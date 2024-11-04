"""Config flow for Nature Remo integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    DOMAIN,
    CONF_COOL_TEMP,
    CONF_HEAT_TEMP,
    DEFAULT_COOL_TEMP,
    DEFAULT_HEAT_TEMP,
    API_ENDPOINT,
)

_LOGGER = logging.getLogger(__name__)

async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> bool:
    """Validate the user input allows us to connect."""
    session = async_get_clientsession(hass)
    headers = {"Authorization": f"Bearer {data[CONF_ACCESS_TOKEN]}"}

    try:
        async with session.get(
            f"{API_ENDPOINT}devices",
            headers=headers,
        ) as response:
            if response.status == 200:
                return True
            return False
    except Exception as error:
        _LOGGER.error("Error validating Nature Remo token: %s", error)
        return False


class NatureRemoConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Nature Remo."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            # Validate the access token
            valid = await validate_input(self.hass, user_input)

            if valid:
                # Create entry
                return self.async_create_entry(
                    title="Nature Remo",
                    data=user_input,
                )
            
            errors["base"] = "invalid_auth"

        # Show form
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ACCESS_TOKEN): str,
                    vol.Optional(
                        CONF_COOL_TEMP,
                        default=DEFAULT_COOL_TEMP
                    ): vol.Coerce(int),
                    vol.Optional(
                        CONF_HEAT_TEMP,
                        default=DEFAULT_HEAT_TEMP
                    ): vol.Coerce(int),
                }
            ),
            errors=errors,
        )

    async def async_step_import(self, import_info: dict[str, Any]) -> FlowResult:
        """Handle import from configuration.yaml."""
        return await self.async_step_user(import_info)
