/** @odoo-module **/

export const MAX_FILE_SIZE = 25 * 1024 * 1024;

export function readFileAsBase64(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => {
            const result = reader.result;
            resolve(result.includes(",") ? result.split(",")[1] : result);
        };
        reader.onerror = (error) => reject(error);
        reader.readAsDataURL(file);
    });
}

export async function collectFiles(fileList, notification) {
    const files = [];
    for (const file of fileList) {
        if (file.size > MAX_FILE_SIZE) {
            notification.add(
                `El archivo ${file.name} supera el tamaño máximo permitido de 25 MB y ha sido omitido.`,
                { type: "danger" }
            );
            continue;
        }
        files.push({
            name: file.name,
            size: file.size,
            mimetype: file.type || "application/pdf",
            data: await readFileAsBase64(file),
        });
    }
    return files;
}
