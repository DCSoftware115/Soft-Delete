from odoo import fields, models, api
from odoo.exceptions import UserError, ValidationError
import logging
_logger = logging.getLogger(__name__)

class BaseModuleUninstall(models.TransientModel):
    _inherit = 'base.module.uninstall'

    select_all_permanent_delete = fields.Boolean(
        string='Select All Models for Deleted Records Permanently Delete',
        default=True
    )
    specific_models_recover = fields.Many2many(
        'ir.model',
        string='Select Specific Model for Records Recover'
    )
    is_soft_delete_module = fields.Boolean(
        string="Is Soft Delete Module",
        compute='_compute_is_soft_delete_module'
    )

    @api.depends('module_id')
    def _compute_is_soft_delete_module(self):
        for record in self:
            record.is_soft_delete_module = record.module_id.name == 'soft_delete'

    @api.depends('module_ids', 'module_id')
    def _compute_model_ids(self):
        """
        Compute the model_ids field, handling both the default case and the special case
        for the soft_delete module.
        """
        for wizard in self:
            if not wizard.module_id:
                wizard.model_ids = [(6, 0, [])]
                continue

            if wizard.module_id.name == 'soft_delete':
                # Get base models from soft.delete.manager.config
                config = self.env['soft.delete.manager.config'].search([], limit=1)
                wizard_model_names = []
                if config and config.model_ids:
                    wizard_model_names = [
                        'x_%s_wizard' % model.model.replace('.', '_')
                        for model in config.model_ids
                    ]
                wizard_models = self.env['ir.model'].search([
                    ('transient', '=', False),
                    ('model', 'in', wizard_model_names)
                ])

                # Properly update name field to readable version
                for model in wizard_models:
                    if model.model.startswith('x_') and model.name == model.model:
                        readable = model.model.replace('x_', '').replace('_wizard', '').replace('_', ' ').title()
                        model.write({'name': readable})

                # Validate that transformed models have the 'x_is_deleted' field
                for model in wizard_models:
                    model_name = model.model
                    # Transform the model name directly for validation
                    if model_name.startswith('x_') and model_name.endswith('_wizard'):
                        transformed_name = model_name[2:-7].replace('_', '.')  # Remove 'x_' and '_wizard', convert to Odoo format
                        if transformed_name in self.env and 'x_is_deleted' not in self.env[transformed_name]._fields:
                            _logger.warning(
                                f"Transformed model '{transformed_name}' (from '{model_name}') is missing the 'x_is_deleted' field required for soft deletion."
                            )
                    else:
                        if model_name in self.env and 'x_is_deleted' not in self.env[model_name]._fields:
                            _logger.warning(
                                f"Model '{model_name}' is missing the 'x_is_deleted' field required for soft deletion."
                            )

                wizard.model_ids = wizard_models
            else:
                # Default logic for other modules
                ir_models = self._get_models()
                ir_models_xids = ir_models._get_external_ids()
                module_names = set(wizard._get_modules().mapped('name'))

                def lost(model):
                    xids = ir_models_xids.get(model.id, ())
                    return xids and all(xid.split('.')[0] in module_names for xid in xids)

                wizard.model_ids = ir_models.filtered(lost).sorted('name')

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if 'select_all_permanent_delete' in fields_list:
            if res.get('specific_models_recover'):
                res['select_all_permanent_delete'] = False
            elif not res.get('specific_models_recover'):
                res['select_all_permanent_delete'] = True
        return res

    @api.constrains('select_all_permanent_delete', 'specific_models_recover')
    def _check_selection_consistency(self):
        for record in self:
            if record.specific_models_recover and record.select_all_permanent_delete:
                raise ValidationError(
                    "You cannot select 'Select All Models for Deleted Records Permanently Delete' "
                    "when specific models are selected for recovery."
                )

    @api.onchange('specific_models_recover')
    def _onchange_specific_models_recover(self):
        if self.specific_models_recover:
            self.select_all_permanent_delete = False
        else:
            self.select_all_permanent_delete = True

    def action_uninstall(self):
        """
        Override the uninstall action to handle soft delete logic for the soft_delete module.
        - Transform model names of the form 'x_<name>_wizard' to '<name>' (e.g., 'x_cargo_short_name_master_wizard' to 'cargo.short.name.master').
        - If select_all_permanent_delete is True, permanently delete records.
        - If specific_models_recover is set, soft delete by setting x_is_deleted = True for all selected models.
        - For non-selected models, permanently delete records where x_is_deleted = True.
        """
        if self.is_soft_delete_module:
            # Validate the state before proceeding
            if self.specific_models_recover and self.select_all_permanent_delete:
                raise UserError(
                    "Invalid selection: You cannot select 'Select All Models for Deleted Records Permanently Delete' "
                    "when specific models are selected for recovery."
                )

            if self.select_all_permanent_delete and not self.specific_models_recover:
                # Permanently delete all records for the models in model_ids
                for model in self.model_ids:
                    model_name = model.model
                    # Transform the model name directly
                    if model_name.startswith('x_') and model_name.endswith('_wizard'):
                        transformed_model = model_name[2:-7].replace('_', '.')  # Remove 'x_' and '_wizard', convert to Odoo format
                        if transformed_model in self.env:
                            self.env[transformed_model].search([]).unlink()  # Permanent deletion
                    else:
                        if model_name in self.env:
                            self.env[model_name].search([]).unlink()  # Permanent deletion
            elif self.specific_models_recover:
                # Handle records for recovery (soft delete) and non-selected models
                for model in self.model_ids:
                    model_name = model.model
                    # Transform the model name directly
                    if model_name.startswith('x_') and model_name.endswith('_wizard'):
                        transformed_model = model_name[2:-7].replace('_', '.')  # Remove 'x_' and '_wizard', convert to Odoo format
                        if transformed_model in self.env:
                            # Check if the transformed model has an 'x_is_deleted' field
                            if 'x_is_deleted' not in self.env[transformed_model]._fields:
                                _logger.warning(
                                    f"Skipping transformed model '{transformed_model}' (from '{model_name}') because it does not have an 'x_is_deleted' field."
                                )
                                continue  # Skip this model

                            if model in self.specific_models_recover:
                                # Soft delete by setting x_is_deleted = True for all selected models
                                self.env[transformed_model].search([('x_is_deleted', '=', False)]).write({'x_is_deleted': True})
                            else:
                                # For non-selected models, permanently delete records where x_is_deleted = True
                                records_to_delete = self.env[transformed_model].search([('x_is_deleted', '=', True)])
                                if records_to_delete:
                                    records_to_delete.unlink()  # Permanently delete
                    else:
                        if model_name in self.env:
                            # Check if the model has an 'x_is_deleted' field
                            if 'x_is_deleted' not in self.env[model_name]._fields:
                                _logger.warning(
                                    f"Skipping model '{model_name}' because it does not have an 'x_is_deleted' field."
                                )
                                continue  # Skip this model

                            if model in self.specific_models_recover:
                                # Soft delete by setting x_is_deleted = True for all selected models
                                self.env[model_name].search([('x_is_deleted', '=', False)]).write({'x_is_deleted': True})
                            else:
                                # For non-selected models, permanently delete records where x_is_deleted = True
                                records_to_delete = self.env[model_name].search([('x_is_deleted', '=', True)])
                                if records_to_delete:
                                    records_to_delete.unlink()  # Permanently delete
            else:
                raise UserError("Please select models to recover or choose to permanently delete all records.")

        # Proceed with the module uninstallation
        return super(BaseModuleUninstall, self).action_uninstall()
