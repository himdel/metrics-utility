#!/usr/bin/env python3
"""Exercise the real gather CLI through a loopback PostgreSQL fault proxy."""

import argparse
import asyncio
import csv
import io
import json
import os
import struct
import sys
import tarfile
import time

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
COPY_MARKER = b'filtered_hosts AS'
CASES = (
    'baseline',
    'startup-close',
    'startup-drop',
    'startup-drop-default',
    'collector-close',
    'collector-drop',
    'streaming-close',
    'second-slice-close',
    'collector-sql-error',
    'second-slice-sql-error',
    'all-sql-error',
    'collector-close-with-vcpu',
)


class Proxy:
    def __init__(self, case, host, port):
        self.case = case
        self.host = host
        self.port = port
        self.matches = 0
        self.triggered = False
        self.writers = []
        self.events = []
        self.started = time.monotonic()
        self.stream_armed = False
        self.copy_data_frames = 0

    def record(self, event):
        self.events.append({'seconds': round(time.monotonic() - self.started, 3), 'event': event})

    def fault(self, payload):
        marker = b'COPY (' if self.case == 'all-sql-error' else COPY_MARKER
        if marker not in payload or self.case == 'baseline' or (self.triggered and self.case != 'all-sql-error'):
            return False
        self.matches += 1
        target = 2 if self.case.startswith('second-slice') else 1
        if self.matches != target and self.case != 'all-sql-error':
            return False
        self.triggered = True
        self.record(f'fault at SQL marker, occurrence {self.matches}')
        return True

    async def client_to_db(self, reader, upstream, client):
        # Startup has no message type; subsequent PostgreSQL frames do.
        length = await reader.readexactly(4)
        payload = await reader.readexactly(struct.unpack('!I', length)[0] - 4)
        upstream.write(length + payload)
        await upstream.drain()
        while True:
            kind = await reader.readexactly(1)
            length = await reader.readexactly(4)
            payload = await reader.readexactly(struct.unpack('!I', length)[0] - 4)
            if self.fault(payload):
                if self.case.endswith('sql-error'):
                    # A real PostgreSQL statement error with the TCP session intact.
                    # This control isolates status reporting from broken-lock cleanup.
                    if kind != b'Q':
                        raise RuntimeError(f'Expected simple COPY query, got {kind!r}')
                    payload = b'COPY (SELECT 1 / 0) TO STDOUT WITH CSV HEADER\0'
                    length = struct.pack('!I', len(payload) + 4)
                elif self.case == 'streaming-close':
                    self.stream_armed = True
                elif self.case.endswith('drop'):
                    await asyncio.Future()  # Hold TCP open but stop forwarding.
                else:
                    client.close()
                    upstream.close()
                    return
            upstream.write(kind + length + payload)
            await upstream.drain()

    async def db_to_client(self, reader, writer, upstream):
        while True:
            kind = await reader.readexactly(1)
            length = await reader.readexactly(4)
            payload = await reader.readexactly(struct.unpack('!I', length)[0] - 4)
            writer.write(kind + length + payload)
            await writer.drain()
            if self.stream_armed and kind == b'd':
                self.copy_data_frames += 1
                if self.copy_data_frames == 2:
                    self.record('closed after forwarding COPY header and first data row')
                    writer.close()
                    upstream.close()
                    return

    async def handle(self, reader, writer):
        self.writers.append(writer)
        self.record('client connected')
        tasks = []
        upstream = None
        try:
            if self.case.startswith('startup') or (self.triggered and not self.case.endswith('sql-error')):
                self.record('connection blocked')
                if self.case.startswith('startup-drop') or self.case.endswith('drop'):
                    await reader.read()
                return
            db_reader, upstream = await asyncio.open_connection(self.host, self.port)
            self.writers.append(upstream)
            tasks = [
                asyncio.create_task(self.client_to_db(reader, upstream, writer)),
                asyncio.create_task(self.db_to_client(db_reader, writer, upstream)),
            ]
            done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                task.result()
        except (asyncio.IncompleteReadError, ConnectionError) as error:
            self.record(type(error).__name__)
        finally:
            for task in tasks:
                task.cancel()
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            writer.close()
            if upstream:
                upstream.close()


def inspect_artifacts(directory):
    archives = []
    for path in sorted(directory.rglob('*.tar.gz')):
        entry = {'path': str(path.relative_to(directory)), 'bytes': path.stat().st_size}
        with tarfile.open(path) as archive:
            entry['members'] = archive.getnames()
            for name in ('manifest.json', 'data_collection_status.csv'):
                member = next((member for member in archive.getmembers() if member.name.removeprefix('./') == name), None)
                if member:
                    data = archive.extractfile(member).read().decode()
                    entry[name] = json.loads(data) if name.endswith('.json') else list(csv.DictReader(io.StringIO(data)))
            for member in archive.getmembers():
                if member.name.removeprefix('./') == 'job_host_summary.csv':
                    entry['job_host_summary_rows'] = sum(1 for _ in csv.DictReader(io.StringIO(archive.extractfile(member).read().decode())))
        archives.append(entry)
    return {
        'archives': archives,
        'remaining_stage_files': [
            {'path': str(path.relative_to(directory)), 'bytes': path.stat().st_size} for path in sorted(directory.glob('tmp/awx_analytics-*/stage/*'))
        ],
        'remaining_stage_directories': [str(path.relative_to(directory)) for path in sorted(directory.glob('tmp/awx_analytics-*/stage'))],
    }


async def run_case(args, case):
    directory = args.output.resolve() / case
    directory.mkdir(parents=True, exist_ok=False)
    (directory / 'tmp').mkdir()
    (directory / 'shipped').mkdir()
    proxy = Proxy(case, args.db_host, args.db_port)
    server = await asyncio.start_server(proxy.handle, '127.0.0.1', 0)
    port = server.sockets[0].getsockname()[1]
    env = {key: value for key, value in os.environ.items() if not key.startswith('METRICS_UTILITY_')}
    env.update(
        METRICS_UTILITY_DB_HOST='127.0.0.1',
        METRICS_UTILITY_DB_PORT=str(port),
        METRICS_UTILITY_DB_NAME=args.db_name,
        METRICS_UTILITY_DB_USER=args.db_user,
        METRICS_UTILITY_DB_PASSWORD=args.db_password,
        METRICS_UTILITY_SHIP_TARGET='directory',
        METRICS_UTILITY_SHIP_PATH=str(directory / 'shipped'),
        METRICS_UTILITY_COLLECTOR_LOCK_SUFFIX=f'connectivity_{case}_{"ship" if args.ship else "dry_run"}',
        TMPDIR=str(directory / 'tmp'),
        PGSSLMODE='disable',
        PGGSSENCMODE='disable',
        PGCONNECT_TIMEOUT='3',
    )
    if case.endswith('with-vcpu'):
        env.update(METRICS_UTILITY_OPTIONAL_COLLECTORS='total_workers_vcpu', METRICS_UTILITY_CLUSTER_NAME='connectivity-reproduction')
    if case == 'startup-drop-default':
        env.pop('PGCONNECT_TIMEOUT')
    command = [
        sys.executable,
        str(ROOT / 'manage.py'),
        'gather_automation_controller_billing_data',
        '--ship' if args.ship else '--dry-run',
        f'--since={args.since}',
        f'--until={args.until}',
    ]
    started = time.monotonic()
    async with server:
        with (directory / 'stdout.log').open('wb') as stdout, (directory / 'stderr.log').open('wb') as stderr:
            process = await asyncio.create_subprocess_exec(*command, cwd=ROOT, env=env, stdout=stdout, stderr=stderr)
            timed_out = False
            try:
                await asyncio.wait_for(process.wait(), args.timeout)
            except TimeoutError:
                timed_out = True
                process.kill()
                await process.wait()
            finally:
                for writer in proxy.writers:
                    writer.close()
    result = {
        'case': case,
        'command': command,
        'returncode': process.returncode,
        'harness_timeout': timed_out,
        'elapsed_seconds': round(time.monotonic() - started, 3),
        'fault_triggered': proxy.triggered or case.startswith('startup'),
        'proxy_events': proxy.events,
        **inspect_artifacts(directory),
    }
    result['shipped_tarballs'] = sum(archive['path'].startswith('shipped/') for archive in result['archives'])
    result['temporary_tarballs'] = sum(archive['path'].startswith('tmp/') for archive in result['archives'])
    (directory / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    if case != 'baseline' and not result['fault_triggered']:
        raise RuntimeError(f'{case}: SQL fault marker was never reached; inspect {directory}')
    if case == 'streaming-close' and proxy.copy_data_frames < 2:
        raise RuntimeError(f'{case}: did not forward a data row; choose an interval containing job-host-summary data')
    print(
        f'{case}: exit={process.returncode}, timeout={timed_out}, '
        f'shipped={result["shipped_tarballs"]}, temporary={result["temporary_tarballs"]}, fault={result["fault_triggered"]}'
    )
    return result


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='New directory for logs, summaries, and tarballs')
    parser.add_argument('--cases', nargs='+', choices=CASES, default=list(CASES))
    parser.add_argument('--db-host', default='127.0.0.1')
    parser.add_argument('--db-port', type=int, default=5432)
    parser.add_argument('--db-name', default='awx')
    parser.add_argument('--db-user', default='awx')
    parser.add_argument('--db-password', default=os.getenv('METRICS_UTILITY_DB_PASSWORD', 'awx'))
    parser.add_argument('--since', default='2025-06-13')
    parser.add_argument('--until', default='2025-06-15')
    parser.add_argument('--timeout', type=float, default=12)
    parser.add_argument('--ship', action='store_true', help='Ship to a private local directory instead of retaining dry-run tarballs')
    args = parser.parse_args()
    results = []
    for case in args.cases:
        results.append(await run_case(args, case))
    (args.output / 'results.json').write_text(json.dumps(results, indent=2) + '\n')


if __name__ == '__main__':
    asyncio.run(main())
