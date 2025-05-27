from odoo import fields, models, api

class BaseModuleUninstall(models.TransientModel):
    _inherit = 'base.module.uninstall'

    is_soft_delete_module = fields.Boolean(
        string="Is Soft Delete Module",
        compute='_compute_is_soft_delete_module'
    )

    @api.depends('module_id')
    def _compute_is_soft_delete_module(self):
        for record in self:
            record.is_soft_delete_module = record.module_id.name == 'soft_delete'

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if 'model_ids' in fields_list and self.env.context.get('active_id'):
            module_id = self.env['ir.module.module'].browse(self.env.context.get('active_id'))
            if module_id.name == 'soft_delete':
                # Get base models from soft.delete.manager.config
                config = self.env['soft.delete.manager.config'].search([], limit=1)
                wizard_model_names = []
                if config and config.model_ids:
                    # Construct wizard model names: x_<model_name>_wizard
                    wizard_model_names = [
                        'x_%s_wizard' % model.model.replace('.', '_')
                        for model in config.model_ids
                    ]
                # Search for transient models matching these names
                wizard_models = self.env['ir.model'].search([
                    ('transient', '=', False),
                    ('model', 'in', wizard_model_names)
                ])
                res['model_ids'] = [(6, 0, wizard_models.ids)]
        return res