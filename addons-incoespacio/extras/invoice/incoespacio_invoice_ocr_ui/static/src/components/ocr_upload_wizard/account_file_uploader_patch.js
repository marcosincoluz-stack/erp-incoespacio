/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { AccountFileUploader } from "@account/components/bills_upload/bills_upload";
import { OcrUploadWizardDialog } from "./ocr_upload_wizard_dialog";
import { useService } from "@web/core/utils/hooks";
import { MAX_FILE_SIZE } from "./ocr_upload_utils";

import { _t } from "@web/core/l10n/translation";

patch(AccountFileUploader.prototype, {
    setup() {
        super.setup();
        this.dialogService = useService("dialog");
        this.stagedOcrFiles = [];
    },

    async onFileUploaded(file) {
        if (file.size > MAX_FILE_SIZE) {
            this.notification.add(
                _t("El archivo '%s' supera el límite máximo permitido de 25 MB y ha sido omitido.", file.name),
                { type: "danger" }
            );
            return;
        }

        // Guardamos los archivos en memoria para presentarlos en el wizard interactivo
        this.stagedOcrFiles.push({
            name: file.name,
            size: file.size,
            mimetype: file.type || "application/pdf",
            data: file.data,
        });
    },

    async onUploadComplete() {
        if (!this.stagedOcrFiles || this.stagedOcrFiles.length === 0) {
            return;
        }

        const filesToStage = [...this.stagedOcrFiles];
        this.stagedOcrFiles = [];

        const context = {
            ...this.extraContext,
            ...(this.env.searchModel ? this.env.searchModel.context : {}),
        };

        // Abrir el popup / wizard modal en el centro de la pantalla
        this.dialogService.add(OcrUploadWizardDialog, {
            initialFiles: filesToStage,
            context: context,
        });
    },
});
