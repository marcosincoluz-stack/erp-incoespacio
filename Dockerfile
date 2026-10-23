FROM odoo:17.0@sha256:0969260596e142c913f1be06e832efcd2347efb440363433c7ef6f24948f40ca
LABEL maintainer="Incoespacio <info@incoespacio.com>"

USER root

COPY requirements.txt /tmp/requirements.txt
RUN pip3 install --no-cache-dir -r /tmp/requirements.txt

USER odoo
