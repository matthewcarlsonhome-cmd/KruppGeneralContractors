"""Procore API integration stub. Requires Procore account with API access.

Procore (https://www.procore.com/) is a cloud-based construction management
platform. This module provides a placeholder client for the Procore REST
API v1.1. When implemented, it will support:

- Syncing daily logs between KruppAI and Procore
- Pulling RFI and submittal data
- Pushing generated documents to project files
- Reading project directory and team information

Setup requirements:
1. Register a Procore Developer App at https://developers.procore.com
2. Obtain OAuth2 client_id and client_secret
3. Configure company_id from your Procore account
4. Set environment variables: PROCORE_CLIENT_ID, PROCORE_CLIENT_SECRET, PROCORE_COMPANY_ID
"""


class ProcoreClient:
    """Placeholder for Procore REST API v1.1 integration.

    This client will handle OAuth2 authentication and provide methods
    for interacting with Procore's project management endpoints.

    Attributes:
        client_id: Procore OAuth2 application client ID.
        client_secret: Procore OAuth2 application client secret.
        company_id: Procore company identifier.
    """

    def __init__(self, client_id: str, client_secret: str, company_id: int) -> None:
        """Initialize the Procore client.

        Args:
            client_id: Procore OAuth2 application client ID.
            client_secret: Procore OAuth2 application client secret.
            company_id: Procore company identifier.

        Raises:
            NotImplementedError: Always — this integration is not yet implemented.
        """
        raise NotImplementedError(
            "Procore integration requires API credentials and is not yet implemented. "
            "See https://developers.procore.com for setup instructions."
        )
