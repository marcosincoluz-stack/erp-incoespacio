FROM odoo:17.0
LABEL maintainer="Incoespacio <info@incoespacio.com>"

USER root

# Instalación de dependencias Python para módulos OCA y AWS
RUN pip3 install --no-cache-dir \
    schwifty \
    boto3 \
    email-validator \
    chardet \
    xlsxwriter \
    xlrd

USER odoo
