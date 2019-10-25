#!/usr/bin/env bash

set -e

# check eniroment if not definded -> set it
: ${POSTGRES_DB=pm_dbh213}
: ${POSTGRES_DB_USER=pmuser_231da}
: ${POSTGRES_USER_PASS=pmpass_2a31da}
: ${POSTGRES_USER=postgres}

POSTGRES="psql --username ${POSTGRES_USER}"

echo "Creating database role: ${POSTGRES_DB_USER}"

$POSTGRES <<-EOSQL
CREATE USER ${POSTGRES_DB_USER} WITH CREATEDB PASSWORD '${POSTGRES_USER_PASS}';
EOSQL

echo "Creating database: ${POSTGRES_DB}"

$POSTGRES <<EOSQL
CREATE DATABASE ${POSTGRES_DB} OWNER ${POSTGRES_DB_USER};
EOSQL