FROM nexus.lan.tribe29.com:5010/sles-12sp3-base

SHELL ["/bin/bash", "-c"]

ARG PACKAGES

RUN zypper addrepo -G http://nexus:8081/repository/sles12sp3 sles12sp3 \
    && zypper addrepo -G http://nexus:8081/repository/sles12spx-web-scripting web-scripting \
    && zypper -n --no-gpg-checks in --replacefiles \
    curl \
    cyrus-sasl-devel \
    enchant-devel \
    git \
    krb5-devel \
    libmysqlclient-devel \
    make \
    nodejs \
    npm \
    openldap2-devel \
    python \
    python-devel \
    python-openssl \
    python-xml \
    rrdtool-devel \
    sudo
RUN curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py \
    && python get-pip.py
RUN pip install --upgrade setuptools \
    && pip install git+https://github.com/pypa/pipenv.git \
    && zypper -n --no-gpg-checks in --replacefiles \
    $PACKAGES \
    && zypper clean -a
