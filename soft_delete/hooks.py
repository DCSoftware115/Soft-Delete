from odoo import api, SUPERUSER_ID
import logging

_logger = logging.getLogger(__name__)

def uninstall_hook(cr, registry):
    """
    Hook to clean up soft delete configurations during module uninstallation.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    try:
        # Use existing config or skip creating a new one
        config = env['soft.delete.manager.config'].search([], limit=1)
        if config:
            env['res.config.settings'].action_cleanup_soft_delete()
        else:
            _logger.warning("No soft delete configuration found; skipping cleanup")
        _logger.info("Successfully executed uninstall cleanup")
    except Exception as e:
        _logger.error(f"Error during uninstall cleanup: {str(e)}")
        raise