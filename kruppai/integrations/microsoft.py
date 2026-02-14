"""Microsoft Graph API stub for SharePoint and Outlook integration.

Microsoft Graph (https://graph.microsoft.com/) provides unified access to
Microsoft 365 services. This module provides a placeholder client for
integrating with SharePoint document libraries and Outlook email. When
implemented, it will support:

- Uploading generated documents to SharePoint project folders
- Sending daily reports and RFIs via Outlook
- Reading project files from SharePoint document libraries
- Calendar integration for meeting minutes scheduling

Setup requirements:
1. Register an application in Azure Active Directory
2. Grant Microsoft Graph API permissions (Files.ReadWrite, Mail.Send, Sites.ReadWrite.All)
3. Obtain tenant_id, client_id, and client_secret
4. Set environment variables: MS_TENANT_ID, MS_CLIENT_ID, MS_CLIENT_SECRET
"""


class MicrosoftGraphClient:
    """Placeholder for Microsoft Graph API integration.

    This client will handle Azure AD authentication and provide methods
    for interacting with SharePoint and Outlook via the Graph API.

    Attributes:
        tenant_id: Azure AD tenant identifier.
        client_id: Azure AD application client ID.
        client_secret: Azure AD application client secret.
    """

    def __init__(self, tenant_id: str, client_id: str, client_secret: str) -> None:
        """Initialize the Microsoft Graph client.

        Args:
            tenant_id: Azure Active Directory tenant identifier.
            client_id: Azure AD registered application client ID.
            client_secret: Azure AD registered application client secret.

        Raises:
            NotImplementedError: Always — this integration is not yet implemented.
        """
        raise NotImplementedError(
            "Microsoft Graph integration requires Azure AD setup and is not yet implemented. "
            "See https://learn.microsoft.com/en-us/graph/overview for documentation."
        )
