"""Sage 300 CRE ODBC integration stub.

Sage 300 CRE (Construction and Real Estate) is an accounting and project
management system widely used in the construction industry. This module
provides a placeholder client for connecting to Sage via ODBC. When
implemented, it will support:

- Reading job cost data for budget forecasting
- Pulling committed cost and subcontract values
- Syncing change order financial data
- Importing cost code structures for estimate reviews

Setup requirements:
1. Install Sage 300 CRE ODBC driver on the host machine
2. Configure a System DSN pointing to the Sage database
3. Obtain read-only database credentials from your Sage administrator
4. Set environment variable: SAGE_CONNECTION_STRING
   Example: "DSN=Sage300CRE;UID=readonly;PWD=password"
"""


class SageClient:
    """Placeholder for Sage 300 CRE ODBC integration.

    This client will manage ODBC connections and provide methods for
    reading financial and project data from Sage 300 CRE.

    Attributes:
        connection_string: ODBC connection string for the Sage database.
    """

    def __init__(self, connection_string: str) -> None:
        """Initialize the Sage 300 CRE client.

        Args:
            connection_string: ODBC connection string
                (e.g., ``"DSN=Sage300CRE;UID=user;PWD=pass"``).

        Raises:
            NotImplementedError: Always — this integration is not yet implemented.
        """
        raise NotImplementedError(
            "Sage 300 CRE integration requires an ODBC driver and is not yet implemented. "
            "Contact your Sage administrator for connection details."
        )
