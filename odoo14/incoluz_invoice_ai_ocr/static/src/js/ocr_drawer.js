odoo.define('incoluz_invoice_ai_ocr.drawer', function (require) {
"use strict";

const core = require('web.core');
const rpc = require('web.rpc');
const Dialog = require('web.Dialog');
const Widget = require('web.Widget');
const viewRegistry = require('web.view_registry');
const AbstractController = require('web.AbstractController');
const FormController = require('web.FormController');
require('account.bills.tree');
require('account.dashboard.kanban');

const qweb = core.qweb;
const _t = core._t;

async function collectFiles(fileList) {
    const files = [];
    const list = Array.from(fileList || []);
    for (let i = 0; i < list.length; i++) {
        const file = list[i];
        if (!file) {
            continue;
        }
        if (file.size > 25 * 1024 * 1024) {
            core.bus.trigger('do-action', {
                action: {
                    type: 'ir.actions.client',
                    tag: 'display_notification',
                    params: {
                        title: _t("OCR IA"),
                        message: _.str.sprintf(_t("El archivo '%s' supera los 25 MB y ha sido omitido."), file.name),
                        type: 'danger',
                        sticky: false,
                    }
                }
            });
            continue;
        }
        const b64 = await new Promise((resolve) => {
            const reader = new FileReader();
            reader.onload = () => {
                const res = reader.result || "";
                resolve(res.includes(',') ? res.split(',')[1] : res);
            };
            reader.onerror = () => {
                console.warn("Error leyendo archivo:", file.name);
                resolve(null);
            };
            reader.onabort = () => resolve(null);
            reader.readAsDataURL(file);
        });
        if (b64) {
            files.push({
                name: file.name,
                size: file.size,
                mimetype: file.type || 'application/pdf',
                data: b64,
            });
        }
    }
    return files;
}

/**
 * Diálogo interactivo para subir facturas por lotes con IA
 */
const OcrUploadDialog = Dialog.extend({
    template: 'incoluz_invoice_ai_ocr.OcrUploadWizardDialog',
    events: _.extend({}, Dialog.prototype.events, {
        'click .o_ocr_drop_area': '_onAddMoreFilesClick',
        'change input.o_ocr_wizard_file_input': '_onFilesSelected',
        'change .o_ocr_move_type_select': '_onMoveTypeChanged',
        'dragover .o_ocr_drop_area': '_onDragOver',
        'dragleave .o_ocr_drop_area': '_onDragLeave',
        'drop .o_ocr_drop_area': '_onDrop',
        'click .o_ocr_remove_btn': '_onRemoveFile',
    }),

    init: function (parent, options) {
        options = options || {};
        const self = this;
        this.context = options.context || {};
        this.controller = parent;
        this.files = (options.initialFiles || []).slice();
        this.selectedMoveType = 'auto';
        this.isProcessing = false;

        const dialogOptions = {
            title: _t("Digitalizar facturas con IA"),
            size: 'medium',
            dialogClass: 'o_ocr_wizard_dialog_wrap',
            $parentNode: options.$parentNode || $('body'),
            buttons: [
                {
                    text: _t("Subir más archivos"),
                    classes: 'btn-outline-primary',
                    click: function () {
                        self._onAddMoreFilesClick();
                    },
                },
                {
                    text: self._getProcessButtonText(),
                    classes: 'btn-primary o_ocr_process_btn',
                    disabled: !self.files.length,
                    click: function () {
                        self._processFiles();
                    },
                },
                {
                    text: _t("Cancelar"),
                    classes: 'btn-secondary',
                    close: true,
                },
            ],
        };

        this._super(parent, dialogOptions);
    },

    formatFileSize: function (bytes) {
        if (!bytes || bytes === 0) {
            return "0 B";
        }
        const k = 1024;
        const sizes = ["B", "KB", "MB", "GB"];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
    },

    _getProcessButtonText: function () {
        return _.str.sprintf(_t("Procesar (%s)"), this.files ? this.files.length : 0);
    },

    _onMoveTypeChanged: function (ev) {
        this.selectedMoveType = $(ev.currentTarget).val();
    },

    _updateView: function () {
        const $newContent = $(qweb.render('incoluz_invoice_ai_ocr.OcrUploadWizardDialog', { widget: this }));
        this.$el.html($newContent.html());
        if (this.$footer) {
            const $btn = this.$footer.find('.o_ocr_process_btn');
            $btn.text(this._getProcessButtonText());
            $btn.prop('disabled', !this.files.length || this.isProcessing);
        }
    },

    _onAddMoreFilesClick: function (ev) {
        if (ev) {
            ev.preventDefault();
        }
        if (!this.isProcessing) {
            this.$('input.o_ocr_wizard_file_input').click();
        }
    },

    _stageFiles: function (fileList) {
        const self = this;
        if (!fileList || !fileList.length) {
            return;
        }
        collectFiles(Array.from(fileList)).then(function (newFiles) {
            self.files = self.files.concat(newFiles);
            self._updateView();
        });
    },

    _onFilesSelected: function (ev) {
        const fileList = ev.target.files;
        ev.target.value = "";
        this._stageFiles(fileList);
    },

    _onDragOver: function (ev) {
        ev.preventDefault();
        this.$('.o_ocr_drop_area').addClass('is-dragging');
    },

    _onDragLeave: function (ev) {
        ev.preventDefault();
        this.$('.o_ocr_drop_area').removeClass('is-dragging');
    },

    _onDrop: function (ev) {
        ev.preventDefault();
        this.$('.o_ocr_drop_area').removeClass('is-dragging');
        const dt = ev.originalEvent ? ev.originalEvent.dataTransfer : ev.dataTransfer;
        this._stageFiles(dt ? dt.files : null);
    },

    _onRemoveFile: function (ev) {
        const index = parseInt($(ev.currentTarget).data('index'), 10);
        if (!isNaN(index) && index >= 0 && index < this.files.length) {
            this.files.splice(index, 1);
            this._updateView();
        }
    },

    _processFiles: function () {
        const self = this;
        if (!this.files.length || this.isProcessing) {
            return;
        }
        this.isProcessing = true;
        const $btn = this.$footer ? this.$footer.find('.o_ocr_process_btn') : null;
        if ($btn) {
            $btn.prop('disabled', true).html('<i class="fa fa-spinner fa-spin mr-1"/> ' + _t("Procesando..."));
            this.$footer.find('button').prop('disabled', true);
        }

        const totalCount = this.files.length;
        const filesPayload = this.files.map(function (f) {
            return {
                name: f.name,
                data: f.data,
                mimetype: f.mimetype,
            };
        });

        const rpcContext = _.extend({}, this.context || {});
        if (this.selectedMoveType === 'auto') {
            rpcContext['default_move_type'] = 'in_invoice';
            rpcContext['default_ocr_auto_classify'] = true;
            delete rpcContext['default_journal_id'];
        } else if (this.selectedMoveType) {
            rpcContext['default_move_type'] = this.selectedMoveType;
            rpcContext['default_ocr_auto_classify'] = false;
        }

        rpc.query({
            model: 'account.move',
            method: 'upload_bills_batch',
            args: [filesPayload],
            context: rpcContext,
        }).then(function (createdMoves) {
            self.close();
            if (createdMoves && createdMoves.length > 0) {
                core.bus.trigger('INCOESPACIO_OCR_BATCH_CREATED', createdMoves);
            }
            core.bus.trigger('do-action', {
                action: {
                    type: 'ir.actions.client',
                    tag: 'display_notification',
                    params: {
                        title: _t("OCR IA"),
                        message: _.str.sprintf(_t("Se han enviado %s factura(s) a la cola de digitalización con IA."), totalCount),
                        type: 'success',
                        sticky: false,
                    }
                }
            });
            core.bus.trigger('INCOESPACIO_OCR_RELOAD');
        }).catch(function (error) {
            self.isProcessing = false;
            if (self.$footer) {
                self.$footer.find('button').prop('disabled', false);
                $btn.text(self._getProcessButtonText());
            }
            core.bus.trigger('do-action', {
                action: {
                    type: 'ir.actions.client',
                    tag: 'display_notification',
                    params: {
                        title: _t("Error OCR IA"),
                        message: (error && error.data && error.data.message)
                            || (error && error.message && error.message.data && error.message.data.message)
                            || (error && typeof error.message === 'string' && error.message)
                            || _t("Error al enviar las facturas a digitalizar."),
                        type: 'danger',
                        sticky: true,
                    }
                }
            });
            console.error("Error al procesar facturas con IA:", error);
        });
    },
});

/**
 * Cajón / Píldora inferior estilo Google Drive para seguimiento en tiempo real
 */
const OcrBatchDrawer = Widget.extend({
    template: 'incoluz_invoice_ai_ocr.OcrBatchDrawer',
    events: {
        'click .o_ocr_batch_pill': '_onToggleMinimize',
        'click .btn-minimize': '_onToggleMinimize',
        'click .btn-close-pill': '_onClose',
        'click .btn-close-card': '_onClose',
        'click .btn-add-more': '_onAddMore',
        'change input.o_ocr_drawer_file_input': '_onDrawerFilesSelected',
        'click .o_ocr_item': '_onItemClick',
    },

    init: function (parent) {
        this._super.apply(this, arguments);
        this.visible = false;
        this.minimized = false;
        this.items = [];
        this.pollTimer = null;
        this._hasAutoMinimized = false;
        core.bus.on('INCOESPACIO_OCR_BATCH_CREATED', this, this.onBatchCreated.bind(this));
    },

    start: function () {
        const self = this;
        return this._super.apply(this, arguments).then(function () {
            self.checkActiveBatch();
            self.pollTimer = setInterval(function () {
                self.pollStatus();
            }, 3000);
        });
    },

    destroy: function () {
        if (this.pollTimer) {
            clearInterval(this.pollTimer);
            this.pollTimer = null;
        }
        core.bus.off('INCOESPACIO_OCR_BATCH_CREATED', this);
        this._super.apply(this, arguments);
    },

    getTotalCount: function () {
        return (this.items && this.items.length) || 0;
    },

    getDoneCount: function () {
        return (this.items || []).filter(function (i) { return i.status === 'done'; }).length;
    },

    getIsComplete: function () {
        return this.getTotalCount() > 0 && (this.items || []).every(function (i) {
            return ['done', 'failed', 'mismatch', 'error'].includes(i.status);
        });
    },

    getProgressPercent: function () {
        const total = this.getTotalCount();
        if (!total) {
            return 0;
        }
        const completed = (this.items || []).filter(function (i) {
            return ['done', 'failed', 'mismatch', 'error'].includes(i.status);
        }).length;
        return Math.round((completed / total) * 100);
    },

    _renderDrawer: function () {
        if (!core.qweb || !core.qweb.has_template('incoluz_invoice_ai_ocr.OcrBatchDrawer')) {
            return;
        }
        const $newEl = $(qweb.render('incoluz_invoice_ai_ocr.OcrBatchDrawer', { widget: this }));
        this.$el.replaceWith($newEl);
        this.setElement($newEl);
    },

    onBatchCreated: function (createdMoves) {
        sessionStorage.removeItem("incoespacio_ocr_dismissed_ids");
        this._hasAutoMinimized = false;
        const self = this;
        if (createdMoves && Array.isArray(createdMoves)) {
            createdMoves.forEach(function (m) {
                if (!self.items.find(function (i) { return i.id === m.id; })) {
                    self.items.push({
                        id: m.id,
                        name: m.name || ("Borrador #" + m.id),
                        filename: m.filename || 'factura.pdf',
                        status: m.status || 'processing',
                        partner: '',
                        amount_total: 0,
                        ref: '',
                        error: '',
                        mismatch: false,
                        mismatch_details: '',
                        is_duplicate: false,
                        iban_status: 'none',
                        move_type_label: '',
                    });
                }
            });
        }
        this.visible = true;
        this.minimized = false;
        this._renderDrawer();
        this.checkActiveBatch();
    },

    pollStatus: function () {
        if (this.visible && !this.isComplete) {
            this.pollActiveItems();
        } else {
            this.checkActiveBatch();
        }
    },

    checkActiveBatch: function () {
        const self = this;
        rpc.query({
            model: 'account.move',
            method: 'get_active_ocr_batch',
            args: [],
        }).then(function (activeItems) {
            const dismissedRaw = sessionStorage.getItem("incoespacio_ocr_dismissed_ids");
            const dismissedIds = dismissedRaw ? JSON.parse(dismissedRaw) : [];

            const items = (activeItems || []).filter(function (i) {
                if (i.status === 'processing' || i.status === 'pending') {
                    return true;
                }
                return !dismissedIds.includes(i.id);
            });

            if (!items.length) {
                if (self.visible) {
                    self.visible = false;
                    self._renderDrawer();
                }
                return;
            }

            self.items = items;
            self.visible = true;
            if (self.isComplete) {
                self.minimized = true;
            }
            self._renderDrawer();
        }).catch(function () {
            // Silencioso
        });
    },

    pollActiveItems: function () {
        if (!this.items.length) {
            return;
        }
        const self = this;
        const ids = this.items.map(function (i) { return i.id; });
        rpc.query({
            model: 'account.move',
            method: 'get_active_ocr_batch',
            args: [ids],
        }).then(function (fresh) {
            let shouldReload = false;
            (fresh || []).forEach(function (s) {
                const item = self.items.find(function (i) { return i.id === s.id; });
                if (!item) {
                    return;
                }
                const prevStatus = item.status;
                item.status = s.status;
                item.filename = s.filename || item.filename;
                item.partner = s.partner || item.partner;
                item.amount_total = s.amount_total || item.amount_total;
                item.name = s.name || item.name;
                item.ref = s.ref || item.ref;
                item.error = s.error || item.error;
                item.mismatch_details = s.mismatch_details || item.mismatch_details;
                item.is_duplicate = s.is_duplicate || item.is_duplicate;
                item.iban_status = s.iban_status || item.iban_status;
                item.move_type_label = s.move_type_label || item.move_type_label;
                if (prevStatus !== s.status && ['done', 'failed', 'mismatch', 'error'].includes(s.status)) {
                    shouldReload = true;
                }
            });
            if (self.isComplete && !self._hasAutoMinimized) {
                self.minimized = true;
                self._hasAutoMinimized = true;
                shouldReload = true;
            }
            if (shouldReload) {
                core.bus.trigger('INCOESPACIO_OCR_RELOAD');
            }
            self._renderDrawer();
        }).catch(function () {
            // Silencioso
        });
    },

    _onToggleMinimize: function (ev) {
        if (ev) {
            ev.stopPropagation();
        }
        this.minimized = !this.minimized;
        this._renderDrawer();
    },

    _onClose: function (ev) {
        if (ev) {
            ev.stopPropagation();
        }
        this.visible = false;
        const ids = this.items.map(function (i) { return i.id; });
        sessionStorage.setItem("incoespacio_ocr_dismissed_ids", JSON.stringify(ids));
        this._renderDrawer();
    },

    _onAddMore: function (ev) {
        if (ev) {
            ev.stopPropagation();
        }
        this.$('input.o_ocr_drawer_file_input').click();
    },

    _onDrawerFilesSelected: function (ev) {
        const fileList = ev.target.files;
        if (!fileList || !fileList.length) {
            return;
        }
        const fileArray = Array.from(fileList);
        ev.target.value = "";
        collectFiles(fileArray).then(function (stagedFiles) {
            if (stagedFiles.length > 0) {
                openOcrUploadDialog(null, stagedFiles, {});
            }
        });
    },

    _onItemClick: function (ev) {
        const moveId = $(ev.currentTarget).data('id');
        if (moveId) {
            core.bus.trigger('do-action', {
                action: {
                    type: 'ir.actions.act_window',
                    res_model: 'account.move',
                    res_id: moveId,
                    views: [[false, 'form']],
                    target: 'current',
                }
            });
        }
    },

    formatCurrency: function (amount) {
        return (Number(amount) || 0).toLocaleString('es-ES', { style: 'currency', currency: 'EUR' });
    },
});

// Definir getters en el prototype para evitar ejecución prematura en _.extend de Odoo 14
Object.defineProperty(OcrBatchDrawer.prototype, 'totalCount', {
    get: function () {
        return this.getTotalCount();
    }
});

Object.defineProperty(OcrBatchDrawer.prototype, 'doneCount', {
    get: function () {
        return this.getDoneCount();
    }
});

Object.defineProperty(OcrBatchDrawer.prototype, 'isComplete', {
    get: function () {
        return this.getIsComplete();
    }
});

Object.defineProperty(OcrBatchDrawer.prototype, 'progressPercent', {
    get: function () {
        return this.getProgressPercent();
    }
});

// Inicialización global del Drawer
let ocrDrawerWidgetInstance = null;
function ensureOcrDrawer() {
    if (!core.qweb || !core.qweb.has_template('incoluz_invoice_ai_ocr.OcrBatchDrawer')) {
        return null;
    }
    if (!ocrDrawerWidgetInstance || ocrDrawerWidgetInstance.isDestroyed()) {
        ocrDrawerWidgetInstance = new OcrBatchDrawer(null);
        ocrDrawerWidgetInstance.appendTo($('body'));
    }
    return ocrDrawerWidgetInstance;
}

// Helper para abrir el diálogo modal de digitalización interactivo
function openOcrUploadDialog(controller, initialFiles, context) {
    const dialog = new OcrUploadDialog(controller, {
        initialFiles: initialFiles || [],
        context: context || {},
        $parentNode: $('body'),
    });
    dialog.open();
    return dialog;
}

// Disparar selector de archivos nativo con selección múltiple y abrir el diálogo interactivo
function promptAndOpenOcrDialog(controller, event) {
    const ctx = _.extend({}, (controller && controller.initialState) ? controller.initialState.context : {});
    if (event && event.currentTarget) {
        const $target = $(event.currentTarget);
        const $record = $target.closest('.o_kanban_record');
        if ($record.length && $record.data('record')) {
            ctx['default_journal_id'] = $record.data('record').id;
        }
        const journalType = $target.attr('journal_type');
        if (journalType === 'sale' || journalType === 'purchase') {
            ctx['default_move_type'] = 'auto';
        }
    }

    const $fileInput = $('<input type="file" multiple="multiple" accept=".pdf,image/*" style="display:none;"/>');
    $('body').append($fileInput);
    $fileInput.one('change', function (ev) {
        const files = ev.target.files;
        if (files && files.length > 0) {
            collectFiles(Array.from(files)).then(function (stagedFiles) {
                $fileInput.remove();
                if (stagedFiles && stagedFiles.length > 0) {
                    openOcrUploadDialog(controller, stagedFiles, ctx);
                }
            }).catch(function (err) {
                $fileInput.remove();
                console.error("Error al preparar facturas:", err);
            });
        } else {
            $fileInput.remove();
        }
    });
    $fileInput.click();
}

// ponytail: mixin ya está copiado en los controllers al require(); parchear el mixin aquí no llega.
['account_tree', 'account_dashboard_kanban'].forEach(function (key) {
    const view = viewRegistry.get(key);
    if (view && view.prototype.config && view.prototype.config.Controller) {
        view.prototype.config.Controller.include({
            _onUpload: function (event) {
                if (event) {
                    event.preventDefault();
                    event.stopPropagation();
                }
                promptAndOpenOcrDialog(this, event);
            },
        });
    }
});
$(document).on('click', '.o_button_upload_bill', function (event) {
    if (event.isDefaultPrevented()) {
        return;
    }
    event.preventDefault();
    event.stopPropagation();
    promptAndOpenOcrDialog(null, event);
});

// 4. Client Action para el menú superior "Digitalizar facturas con IA"
core.action_registry.add('incoluz_invoice_ai_ocr.upload_wizard_action', function (parent, action) {
    const ctx = _.extend({}, action.context || {});
    openOcrUploadDialog(parent, [], ctx);
});

AbstractController.include({
    init: function () {
        this._super.apply(this, arguments);
        core.bus.on('INCOESPACIO_OCR_RELOAD', this, this._onOcrReload);
    },
    destroy: function () {
        core.bus.off('INCOESPACIO_OCR_RELOAD', this, this._onOcrReload);
        this._super.apply(this, arguments);
    },
    _onOcrReload: function () {
        if (this.isDestroyed() || this.modelName !== 'account.move') {
            return;
        }
        if (this.$el && this.$el.is(':visible')) {
            this.reload();
        }
    },
});

// 5. Polling automático en vista formulario y control de Split View (lado a lado)
if (FormController) {
    FormController.include({
        start: async function () {
            const res = await this._super.apply(this, arguments);
            this._checkOcrPolling();
            this._checkSplitViewClass();
            return res;
        },
        update: async function (params, options) {
            const res = await this._super.apply(this, arguments);
            this._checkOcrPolling();
            this._checkSplitViewClass();
            return res;
        },
        reload: async function () {
            const res = await this._super.apply(this, arguments);
            this._checkSplitViewClass();
            return res;
        },
        _renderView: function () {
            const self = this;
            return this._super.apply(this, arguments).then(function (res) {
                self._checkSplitViewClass();
                return res;
            });
        },
        destroy: function () {
            this._stopOcrPolling();
            this._super.apply(this, arguments);
        },
        _stopOcrPolling: function () {
            if (this._ocrPollingTimer) {
                clearInterval(this._ocrPollingTimer);
                this._ocrPollingTimer = null;
            }
        },
        _checkSplitViewClass: function () {
            if (!this.model || !this.handle) {
                return;
            }
            const record = this.model.get(this.handle);
            const isSplit = !!(record && record.data && record.data.ocr_show_split_view && record.data.ocr_has_pdf);
            if (this.$el) {
                this.$el.toggleClass('o_invoice_split_view_active', isSplit);
            }
            const $sheetBg = this.$('.o_form_sheet_bg');
            if ($sheetBg.length) {
                $sheetBg.toggleClass('o_invoice_split_view_active', isSplit);
            }
        },
        _checkOcrPolling: function () {
            this._stopOcrPolling();
            if (!this.model || !this.handle) {
                return;
            }
            const record = this.model.get(this.handle);
            if (!record || record.model !== 'account.move' || !record.res_id) {
                return;
            }
            const ocrStatus = record.data && record.data.ocr_status;
            if (ocrStatus === 'processing' || ocrStatus === 'pending') {
                const moveId = record.res_id;
                const self = this;
                this._ocrPollingTimer = setInterval(function () {
                    if (self.isDestroyed()) {
                        self._stopOcrPolling();
                        return;
                    }
                    rpc.query({
                        model: 'account.move',
                        method: 'read',
                        args: [[moveId], ['ocr_status']],
                    }).then(function (res) {
                        if (self.isDestroyed()) {
                            self._stopOcrPolling();
                            return;
                        }
                        if (res && res.length && res[0].ocr_status !== 'processing' && res[0].ocr_status !== 'pending') {
                            self._stopOcrPolling();
                            self.reload();
                            core.bus.trigger('INCOESPACIO_OCR_BATCH_CREATED');
                            if (res[0].ocr_status === 'done') {
                                core.bus.trigger('do-action', {
                                    action: {
                                        type: 'ir.actions.client',
                                        tag: 'display_notification',
                                        params: {
                                            title: _t("🤖 IncoBot: OCR IA"),
                                            message: _t("¡Factura digitalizada con éxito! Los datos han sido actualizados."),
                                            type: 'success',
                                            sticky: false,
                                        }
                                    }
                                });
                            }
                        }
                    }).catch(function () {
                        // Silencioso
                    });
                }, 2000);
            }
        },
    });
}

core.bus.on('web_client_ready', null, function () {
    ensureOcrDrawer();
});

return {
    OcrBatchDrawer,
    OcrUploadDialog,
    openOcrUploadDialog,
    promptAndOpenOcrDialog,
};
});
