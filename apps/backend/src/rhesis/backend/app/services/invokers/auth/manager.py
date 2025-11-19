"""Authentication management for endpoint invokers."""

from datetime import datetime, timedelta
from typing import Optional

import requests
from fastapi import HTTPException
from sqlalchemy.orm import Session

from rhesis.backend.app.models.endpoint import Endpoint
from rhesis.backend.app.models.enums import EndpointAuthType


class AuthenticationManager:
    """Handles authentication token management for endpoints."""

    @staticmethod
    def get_valid_token(db: Session, endpoint: Endpoint) -> Optional[str]:
        """
        Get a valid authentication token based on the endpoint's auth type.

        Checks for cached token first, then obtains a new one if needed.

        Args:
            db: Database session
            endpoint: Endpoint configuration

        Returns:
            Valid authentication token or None
        """
        # Check if we have a valid cached token
        if endpoint.last_token and endpoint.last_token_expires_at:
            if endpoint.last_token_expires_at > datetime.utcnow():
                return endpoint.last_token

        # No valid cached token, get new one based on auth type
        if endpoint.auth_type == EndpointAuthType.BEARER_TOKEN.value:
            return endpoint.auth_token
        elif endpoint.auth_type == EndpointAuthType.CLIENT_CREDENTIALS.value:
            return AuthenticationManager.get_client_credentials_token(db, endpoint)

        return None

    @staticmethod
    def get_client_credentials_token(db: Session, endpoint: Endpoint) -> str:
        """
        Get a new token using OAuth 2.0 client credentials flow.

        Args:
            db: Database session
            endpoint: Endpoint configuration with OAuth details

        Returns:
            Access token

        Raises:
            HTTPException: If token request fails
        """
        if not endpoint.token_url:
            raise HTTPException(
                status_code=400, detail="Token URL is required for client credentials flow"
            )

        # Prepare token request
        payload = {
            "client_id": endpoint.client_id,
            "client_secret": endpoint.client_secret,
            "audience": endpoint.audience,
            "grant_type": "client_credentials",
        }

        # Add scopes if configured
        if endpoint.scopes:
            payload["scope"] = " ".join(endpoint.scopes)

        # Add extra payload if configured
        if endpoint.extra_payload:
            payload.update(endpoint.extra_payload)

        try:
            # Make token request
            response = requests.post(endpoint.token_url, json=payload)
            response.raise_for_status()
            token_data = response.json()

            # Update endpoint with new token info
            endpoint.last_token = token_data["access_token"]
            endpoint.last_token_expires_at = datetime.utcnow() + timedelta(
                seconds=token_data.get("expires_in", 3600)
            )
            # Transaction commit is handled by the session context manager

            return endpoint.last_token
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Failed to get client credentials token: {str(e)}"
            )
