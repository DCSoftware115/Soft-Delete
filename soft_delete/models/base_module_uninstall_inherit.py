from odoo import fields, models, api

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

                res['model_ids'] = [(6, 0, wizard_models.ids)]
                # Ensure select_all_permanent_delete is False if specific_models_recover is set
                if res.get('specific_models_recover'):
                    res['select_all_permanent_delete'] = False
                # Set True if specific_models_recover is empty
                elif not res.get('specific_models_recover'):
                    res['select_all_permanent_delete'] = True
        return res

    @api.onchange('specific_models_recover')
    def _onchange_specific_models_recover(self):
        if self.specific_models_recover:
            self.select_all_permanent_delete = False
        else:
            self.select_all_permanent_delete = True
