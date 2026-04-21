from metrics_utility.anonymized_rollups.base_anonymized_rollup import BaseAnonymizedRollup
from metrics_utility.anonymized_rollups.helpers import sanitize_json


class CredentialsAnonymizedRollup(BaseAnonymizedRollup):
    """
    Collector - credentials_service collector data
    """

    def __init__(self):
        super().__init__('credentials')
        self.collector_names = ['credentials_service']

    # prepare is called for each batch of data
    # result of prepare is merged with other batches using merge function
    # prepare should return JSON (dict) structure
    # dataframe has:
    # credential_type - name of the credential type
    # job_id - id of the job
    # model - job model (job_type)

    def prepare(self, dataframe):
        """
        Batch processing that extracts unique credential types in this batch.
        Returns a sorted list of unique credential type names.
        """
        # Convert ID columns to strings at the beginning
        dataframe = self._convert_id_columns_to_strings(dataframe)

        if dataframe.empty:
            return []

        # Check if credential_type column exists (required for processing)
        if 'credential_type' not in dataframe.columns:
            return []

        # Get unique credential types in this batch
        unique_credential_types = dataframe['credential_type'].dropna().unique()
        # Convert to sorted list of strings
        return sanitize_json(sorted([str(ct) for ct in unique_credential_types]))

    def merge(self, data_all, data_new):
        """
        Merge two credential type lists by unioning them.
        """
        # Handle initial None case (first iteration from load_anonymized_rollup_data)
        if data_all is None:
            return data_new

        return sorted(set(data_all) | set(data_new))
