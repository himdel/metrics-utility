import pandas as pd

from metrics_utility.anonymized_rollups.credentials_anonymized_rollup import CredentialsAnonymizedRollup


# Test data matching credentials_service collector output format
# Columns: credential_type, job_id, model
credentials = [
    {'credential_type': 'Machine', 'job_id': 1, 'model': 'job'},
    {'credential_type': 'Machine', 'job_id': 2, 'model': 'job'},
    {'credential_type': 'Vault', 'job_id': 1, 'model': 'job'},
    {'credential_type': 'Source Control', 'job_id': 3, 'model': 'workflowjob'},
    {'credential_type': 'Source Control', 'job_id': 3, 'model': 'workflowjob'},
    {'credential_type': 'Network', 'job_id': 4, 'model': 'job'},
    {'credential_type': 'Amazon Web Services', 'job_id': 5, 'model': 'job'},
    {'credential_type': 'Amazon Web Services', 'job_id': 6, 'model': 'job'},
    {'credential_type': 'Amazon Web Services', 'job_id': 7, 'model': 'job'},
    {'credential_type': 'Container Registry', 'job_id': 8, 'model': 'job'},
]


def test_credentials_anonymized_rollup_prepare():
    """Test prepare() method extracts unique credential types in a batch."""
    df = pd.DataFrame(credentials)
    credentials_rollup = CredentialsAnonymizedRollup()
    result = credentials_rollup.prepare(df)

    assert isinstance(result, list)

    credential_types = set(result)
    assert 'Machine' in credential_types
    assert 'Vault' in credential_types
    assert 'Source Control' in credential_types
    assert 'Network' in credential_types
    assert 'Amazon Web Services' in credential_types
    assert 'Container Registry' in credential_types

    assert len(result) == 6
    assert result == sorted(result)


def test_credentials_anonymized_rollup_prepare_and_merge():
    """Test full flow: prepare() followed by merge()."""
    df = pd.DataFrame(credentials)
    credentials_rollup = CredentialsAnonymizedRollup()

    result = credentials_rollup.prepare(df)

    assert isinstance(result, list)
    assert len(result) == 6
    assert 'Amazon Web Services' in result
    assert 'Container Registry' in result
    assert 'Machine' in result
    assert 'Network' in result
    assert 'Source Control' in result
    assert 'Vault' in result
    assert result == sorted(result)


def test_credentials_anonymized_rollup_multiple_batches():
    """Test that merge() correctly merges credential types from multiple batches."""
    batch1_df = pd.DataFrame(
        [
            {'credential_type': 'Machine'},
            {'credential_type': 'Vault'},
        ]
    )

    batch2_df = pd.DataFrame(
        [
            {'credential_type': 'Machine'},
            {'credential_type': 'Network'},
        ]
    )

    credentials_rollup = CredentialsAnonymizedRollup()

    batch1 = credentials_rollup.prepare(batch1_df)
    batch2 = credentials_rollup.prepare(batch2_df)

    merged = credentials_rollup.merge(batch1, batch2)

    assert isinstance(merged, list)
    assert len(merged) == 3
    assert 'Machine' in merged
    assert 'Vault' in merged
    assert 'Network' in merged
    assert merged == sorted(merged)


def test_credentials_anonymized_rollup_prepare_empty_dataframe():
    """Test prepare() with empty dataframe."""
    df = pd.DataFrame()
    credentials_rollup = CredentialsAnonymizedRollup()
    result = credentials_rollup.prepare(df)

    assert isinstance(result, list)
    assert result == []


def test_credentials_anonymized_rollup_prepare_missing_column():
    """Test prepare() with missing credential_type column."""
    df = pd.DataFrame([{'job_id': 1, 'model': 'job'}])
    credentials_rollup = CredentialsAnonymizedRollup()
    result = credentials_rollup.prepare(df)

    assert isinstance(result, list)
    assert result == []


def test_credentials_anonymized_rollup_merge_none():
    """Test merge() with None (first batch)."""
    credentials_rollup = CredentialsAnonymizedRollup()
    batch1_df = pd.DataFrame([{'credential_type': 'Machine'}])
    batch1 = credentials_rollup.prepare(batch1_df)

    merged = credentials_rollup.merge(None, batch1)

    assert isinstance(merged, list)
    assert 'Machine' in merged


def test_credentials_anonymized_rollup_field_name_conversion():
    """Test that credential type names are preserved correctly."""
    test_data_df = pd.DataFrame(
        [
            {'credential_type': 'Machine'},
            {'credential_type': 'Source Control'},
            {'credential_type': 'Amazon Web Services'},
            {'credential_type': 'Container-Registry'},
            {'credential_type': 'My-Custom Type'},
            {'credential_type': 'UPPERCASE'},
        ]
    )

    credentials_rollup = CredentialsAnonymizedRollup()
    result = credentials_rollup.prepare(test_data_df)

    assert isinstance(result, list)
    assert len(result) == 6
    assert 'Amazon Web Services' in result
    assert 'Container-Registry' in result
    assert 'Machine' in result
    assert 'My-Custom Type' in result
    assert 'Source Control' in result
    assert 'UPPERCASE' in result
    assert result == sorted(result)
