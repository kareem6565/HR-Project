FROM php:8.2-fpm-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 libpq-dev \
    && docker-php-ext-install -j"$(nproc)" pdo_pgsql \
    && rm -rf /var/lib/apt/lists/*

COPY php.ini "$PHP_INI_DIR/conf.d/hr-manager.ini"

WORKDIR /var/www/html

EXPOSE 9000

CMD ["php-fpm"]
