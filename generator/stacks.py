"""
Connection hints for the builder: which env vars does container A need to reach container B.
Stack templates are stored in the database (StackTemplate model) and loaded via
the load_stacks management command from fixtures/stack_templates.json.
"""

# Verbindungs-Mapping: welche Env-Vars braucht Container A um Container B zu erreichen
CONNECTION_HINTS = {
    'postgres': {
        5432: ['DB_HOST=127.0.0.1', 'DB_PORT=5432', 'DATABASE_URL=postgresql://user:pass@127.0.0.1:5432/dbname'],
    },
    'mariadb': {
        3306: ['DB_HOST=127.0.0.1', 'DB_PORT=3306', 'DATABASE_URL=mysql://user:pass@127.0.0.1:3306/dbname'],
    },
    'mysql': {
        3306: ['DB_HOST=127.0.0.1', 'DB_PORT=3306', 'DATABASE_URL=mysql://user:pass@127.0.0.1:3306/dbname'],
    },
    'redis': {
        6379: ['REDIS_URL=redis://127.0.0.1:6379', 'REDIS_HOST=127.0.0.1', 'REDIS_PORT=6379'],
    },
    'valkey': {
        6379: ['REDIS_URL=redis://127.0.0.1:6379', 'REDIS_HOST=127.0.0.1', 'REDIS_PORT=6379'],
    },
    'mongodb': {
        27017: ['MONGO_URL=mongodb://127.0.0.1:27017', 'MONGODB_HOST=127.0.0.1', 'MONGODB_PORT=27017'],
    },
    'mongo': {
        27017: ['MONGO_URL=mongodb://127.0.0.1:27017', 'MONGODB_HOST=127.0.0.1', 'MONGODB_PORT=27017'],
    },
    'influxdb': {
        8086: ['INFLUXDB_URL=http://127.0.0.1:8086', 'INFLUXDB_HOST=127.0.0.1'],
    },
    'memcached': {
        11211: ['MEMCACHED_HOST=127.0.0.1', 'MEMCACHED_PORT=11211'],
    },
    'rabbitmq': {
        5672: ['RABBITMQ_URL=amqp://user:pass@127.0.0.1:5672', 'RABBITMQ_HOST=127.0.0.1'],
    },
    'minio': {
        9000: ['S3_ENDPOINT=http://127.0.0.1:9000', 'S3_HOST=127.0.0.1', 'S3_PORT=9000'],
    },
}
