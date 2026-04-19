import base64
from django.test import TestCase
from .views import (
    _classify_db_connections,
    _build_mysql_init_sql,
    _build_postgres_init_sql,
    _inject_db_init,
    validate_form_data,
)


def _make_form(containers, init_containers=None, pod_name='testpod'):
    return {
        'pod_name': pod_name,
        'mode': 'rootless',
        'restart_policy': 'Always',
        'containers': containers,
        'init_containers': init_containers or [],
    }


def _c(name, image, env='', volumes='', ports=''):
    return {'name': name, 'image': image, 'env': env, 'volumes': volumes, 'ports': ports}


class ContainerPortConflictTests(TestCase):

    def test_same_container_port_error(self):
        fd = _make_form([
            _c('wordpress', 'docker.io/wordpress:latest', ports='8080:80'),
            _c('nextcloud', 'docker.io/nextcloud:latest', ports='8090:80'),
        ])
        warnings = validate_form_data(fd)
        errors = [w for w in warnings if w['level'] == 'error' and 'containerPort: 80' in w.get('hint', '')]
        self.assertEqual(len(errors), 1)
        self.assertIn('wordpress', errors[0]['msg'])
        self.assertIn('nextcloud', errors[0]['msg'])

    def test_different_container_ports_ok(self):
        fd = _make_form([
            _c('app1', 'docker.io/nginx:latest', ports='8080:80'),
            _c('app2', 'docker.io/nginx:latest', ports='8090:8080'),
        ])
        warnings = validate_form_data(fd)
        port_errors = [w for w in warnings if 'containerPort' in w.get('hint', '')]
        self.assertEqual(port_errors, [])

    def test_no_ports_no_error(self):
        fd = _make_form([
            _c('db', 'docker.io/mariadb:11', env='MARIADB_ROOT_PASSWORD=x', volumes='db:/var/lib/mysql'),
        ])
        warnings = validate_form_data(fd)
        port_errors = [w for w in warnings if 'containerPort' in w.get('hint', '')]
        self.assertEqual(port_errors, [])


class ClassifyDbConnectionsTests(TestCase):

    def test_no_db_container(self):
        fd = _make_form([_c('app', 'docker.io/nginx:latest')])
        result = _classify_db_connections(fd)
        self.assertEqual(result, {})

    def test_single_mariadb(self):
        fd = _make_form([
            _c('db', 'docker.io/mariadb:11', 'MARIADB_USER=wp\nMARIADB_PASSWORD=pass\nMARIADB_DATABASE=wp'),
            _c('wp', 'docker.io/wordpress:latest',
               'WORDPRESS_DB_HOST=127.0.0.1\nWORDPRESS_DB_USER=wp\nWORDPRESS_DB_PASSWORD=pass\nWORDPRESS_DB_NAME=wp'),
        ])
        result = _classify_db_connections(fd)
        self.assertIn('mysql', result)
        self.assertEqual(result['mysql']['primary']['user'], 'wp')
        self.assertEqual(len(result['mysql']['apps']), 1)
        self.assertEqual(result['mysql']['apps'][0]['name'], 'wp')

    def test_remote_host_ignored(self):
        fd = _make_form([
            _c('db', 'docker.io/mariadb:11', 'MARIADB_USER=wp\nMARIADB_DATABASE=wp'),
            _c('app', 'docker.io/wordpress:latest',
               'WORDPRESS_DB_HOST=192.168.1.5\nWORDPRESS_DB_USER=other\nWORDPRESS_DB_NAME=other'),
        ])
        result = _classify_db_connections(fd)
        self.assertIn('mysql', result)
        self.assertEqual(len(result['mysql']['apps']), 0)

    def test_host_with_port(self):
        """127.0.0.1:3306 soll als lokal erkannt werden."""
        fd = _make_form([
            _c('db', 'docker.io/mariadb:11', 'MARIADB_USER=wp\nMARIADB_DATABASE=wp'),
            _c('app', 'docker.io/wordpress:latest',
               'WORDPRESS_DB_HOST=127.0.0.1:3306\nWORDPRESS_DB_USER=nc\nWORDPRESS_DB_NAME=nc'),
        ])
        result = _classify_db_connections(fd)
        self.assertEqual(len(result['mysql']['apps']), 1)

    def test_postgres(self):
        fd = _make_form([
            _c('db', 'docker.io/postgres:16', 'POSTGRES_USER=app\nPOSTGRES_PASSWORD=pass\nPOSTGRES_DB=app'),
            _c('app', 'docker.io/nextcloud:latest',
               'POSTGRES_HOST=127.0.0.1\nPOSTGRES_USER=nc\nPOSTGRES_PASSWORD=ncpass\nPOSTGRES_DB=nc'),
        ])
        result = _classify_db_connections(fd)
        self.assertIn('postgres', result)
        self.assertEqual(result['postgres']['primary']['user'], 'app')
        self.assertEqual(result['postgres']['apps'][0]['user'], 'nc')


class BuildMysqlInitSqlTests(TestCase):

    def test_basic(self):
        primary = {'user': 'primary', 'db': 'primarydb'}
        extra = [{'name': 'wp', 'user': 'wordpress', 'pass': 'secret', 'db': 'wordpress'}]
        sql, added = _build_mysql_init_sql(primary, extra)
        self.assertIn('CREATE DATABASE IF NOT EXISTS `wordpress`', sql)
        self.assertIn("CREATE USER IF NOT EXISTS 'wordpress'@'%'", sql)
        self.assertIn("GRANT ALL PRIVILEGES ON `wordpress`.*", sql)
        self.assertIn('FLUSH PRIVILEGES', sql)
        self.assertEqual(added, ['wp'])

    def test_empty_user_and_db_skipped(self):
        """App ohne user und db → kein SQL (skip logic in builder)."""
        primary = {'user': 'app', 'db': 'appdb'}
        extra = [{'name': 'empty', 'user': '', 'pass': 'x', 'db': ''}]
        sql, added = _build_mysql_init_sql(primary, extra)
        self.assertEqual(added, [])
        self.assertEqual(sql, '')

    def test_password_quoting(self):
        primary = {'user': 'x', 'db': 'x'}
        extra = [{'name': 'a', 'user': 'user', 'pass': "pass'with'quotes", 'db': 'db'}]
        sql, _ = _build_mysql_init_sql(primary, extra)
        self.assertIn("IDENTIFIED BY 'pass''with''quotes'", sql)

    def test_backtick_in_db_name(self):
        primary = {'user': 'x', 'db': 'x'}
        extra = [{'name': 'a', 'user': 'u', 'pass': 'p', 'db': 'my`db'}]
        sql, _ = _build_mysql_init_sql(primary, extra)
        self.assertIn('`my``db`', sql)


class BuildPostgresInitSqlTests(TestCase):

    def test_basic(self):
        primary = {'user': 'primary', 'db': 'primarydb'}
        extra = [{'name': 'nc', 'user': 'nextcloud', 'pass': 'ncpass', 'db': 'nextcloud'}]
        sql, added = _build_postgres_init_sql(primary, extra)
        self.assertIn('CREATE ROLE "nextcloud"', sql)
        self.assertIn("rolname = 'nextcloud'", sql)
        self.assertIn('CREATE DATABASE "nextcloud"', sql)
        self.assertIn('GRANT ALL PRIVILEGES ON DATABASE "nextcloud"', sql)
        self.assertEqual(added, ['nc'])

    def test_empty_user_and_db_skipped(self):
        """App ohne user und db → kein SQL."""
        primary = {'user': 'app', 'db': 'app'}
        extra = [{'name': 'x', 'user': '', 'pass': 'p', 'db': ''}]
        sql, added = _build_postgres_init_sql(primary, extra)
        self.assertEqual(added, [])

    def test_password_quoting(self):
        primary = {'user': 'x', 'db': 'x'}
        extra = [{'name': 'a', 'user': 'u', 'pass': "it's'quoted", 'db': 'db'}]
        sql, _ = _build_postgres_init_sql(primary, extra)
        self.assertIn("PASSWORD 'it''s''quoted'", sql)


class InjectDbInitTests(TestCase):

    def test_no_inject_single_app(self):
        """1 App, gleiche Credentials wie primary → kein Init-Container."""
        fd = _make_form([
            _c('db', 'docker.io/mariadb:11',
               'MARIADB_USER=wp\nMARIADB_PASSWORD=secret\nMARIADB_DATABASE=wp\nMARIADB_ROOT_PASSWORD=root'),
            _c('wp', 'docker.io/wordpress:latest',
               'WORDPRESS_DB_HOST=127.0.0.1\nWORDPRESS_DB_USER=wp\nWORDPRESS_DB_PASSWORD=secret\nWORDPRESS_DB_NAME=wp'),
        ])
        notices = _inject_db_init(fd)
        self.assertEqual(fd['init_containers'], [])
        self.assertEqual(notices, [])

    def test_inject_mysql_two_apps(self):
        """MariaDB + WordPress (primary) + Nextcloud (extra) → Init-Container wird injiziert."""
        fd = _make_form([
            _c('db', 'docker.io/mariadb:11',
               'MARIADB_USER=wordpress\nMARIADB_PASSWORD=wppass\nMARIADB_DATABASE=wordpress\nMARIADB_ROOT_PASSWORD=root'),
            _c('wp', 'docker.io/wordpress:latest',
               'WORDPRESS_DB_HOST=127.0.0.1\nWORDPRESS_DB_USER=wordpress\nWORDPRESS_DB_PASSWORD=wppass\nWORDPRESS_DB_NAME=wordpress'),
            _c('nc', 'docker.io/nextcloud:latest',
               'MYSQL_HOST=127.0.0.1\nMYSQL_USER=nextcloud\nMYSQL_PASSWORD=ncpass\nMYSQL_DATABASE=nextcloud'),
        ])
        notices = _inject_db_init(fd)
        self.assertEqual(len(fd['init_containers']), 1)
        ic = fd['init_containers'][0]
        self.assertEqual(ic['name'], 'db-init-mysql')
        self.assertEqual(ic['image'], 'docker.io/busybox:latest')
        # SQL im base64-encoded args prüfen
        b64 = ic['args'].split('echo ')[1].split(' |')[0]
        sql = base64.b64decode(b64).decode()
        self.assertIn('CREATE DATABASE IF NOT EXISTS `nextcloud`', sql)
        self.assertIn("CREATE USER IF NOT EXISTS 'nextcloud'@'%'", sql)
        # DB-Container bekommt extra Volume-Mount
        db_c = next(c for c in fd['containers'] if c['name'] == 'db')
        self.assertIn('/docker-entrypoint-initdb.d', db_c['volumes'])
        # Info-Notice vorhanden
        self.assertEqual(len(notices), 1)
        self.assertEqual(notices[0]['level'], 'info')

    def test_inject_postgres_two_apps(self):
        """Postgres + 2 Apps → idempotentes SQL."""
        fd = _make_form([
            _c('db', 'docker.io/postgres:16',
               'POSTGRES_USER=app1\nPOSTGRES_PASSWORD=p1\nPOSTGRES_DB=app1'),
            _c('app1', 'docker.io/myapp:latest',
               'POSTGRES_HOST=127.0.0.1\nPOSTGRES_USER=app1\nPOSTGRES_PASSWORD=p1\nPOSTGRES_DB=app1'),
            _c('app2', 'docker.io/otherapp:latest',
               'POSTGRES_HOST=127.0.0.1\nPOSTGRES_USER=app2\nPOSTGRES_PASSWORD=p2\nPOSTGRES_DB=app2'),
        ])
        notices = _inject_db_init(fd)
        self.assertEqual(len(fd['init_containers']), 1)
        ic = fd['init_containers'][0]
        self.assertEqual(ic['name'], 'db-init-postgres')
        b64 = ic['args'].split('echo ')[1].split(' |')[0]
        sql = base64.b64decode(b64).decode()
        self.assertIn('CREATE ROLE "app2"', sql)
        self.assertIn('CREATE DATABASE "app2"', sql)
        self.assertNotIn('app1', sql)  # primary wird nicht doppelt angelegt

    def test_no_double_inject(self):
        """_inject_db_init zweimal aufgerufen → kein doppelter Init-Container."""
        fd = _make_form([
            _c('db', 'docker.io/mariadb:11',
               'MARIADB_USER=wp\nMARIADB_PASSWORD=p\nMARIADB_DATABASE=wp\nMARIADB_ROOT_PASSWORD=r'),
            _c('nc', 'docker.io/nextcloud:latest',
               'MYSQL_HOST=127.0.0.1\nMYSQL_USER=nc\nMYSQL_PASSWORD=p\nMYSQL_DATABASE=nc'),
        ])
        _inject_db_init(fd)
        _inject_db_init(fd)
        self.assertEqual(len(fd['init_containers']), 1)

    def test_no_inject_empty_credentials(self):
        """App ohne user/db Vars → kein Inject."""
        fd = _make_form([
            _c('db', 'docker.io/mariadb:11', 'MARIADB_ROOT_PASSWORD=root'),
            _c('app', 'docker.io/nginx:latest', 'FOO=bar'),
        ])
        notices = _inject_db_init(fd)
        self.assertEqual(fd['init_containers'], [])
        self.assertEqual(notices, [])


class CredentialSymmetryWithInitContainerTests(TestCase):

    def test_no_false_positive_when_init_container_present(self):
        """Wenn db-init-postgres vorhanden, kein Credential-Mismatch-Error."""
        fd = _make_form([
            _c('db', 'docker.io/postgres:16',
               'POSTGRES_USER=appuser\nPOSTGRES_PASSWORD=dbpass\nPOSTGRES_DB=appdb'),
            _c('nc', 'docker.io/nextcloud:latest',
               'POSTGRES_HOST=127.0.0.1\nPOSTGRES_USER=nextcloud\nPOSTGRES_PASSWORD=ncpass\nPOSTGRES_DB=nextcloud'),
        ], init_containers=[{
            'name': 'db-init-postgres', 'image': 'docker.io/busybox:latest',
            'command': 'sh', 'args': '-c "echo test"', 'volumes': 'vol:/db-init', 'env': '',
        }])
        warnings = validate_form_data(fd)
        mismatch = [w for w in warnings if 'mismatch' in w.get('msg', '')]
        self.assertEqual(mismatch, [])

    def test_mismatch_still_fires_without_init_container(self):
        """Ohne Init-Container feuert Check #13 wie gewohnt."""
        fd = _make_form([
            _c('db', 'docker.io/postgres:16',
               'POSTGRES_USER=appuser\nPOSTGRES_PASSWORD=dbpass\nPOSTGRES_DB=appdb'),
            _c('nc', 'docker.io/nextcloud:latest',
               'POSTGRES_HOST=127.0.0.1\nPOSTGRES_USER=nextcloud\nPOSTGRES_PASSWORD=ncpass\nPOSTGRES_DB=nextcloud'),
        ])
        warnings = validate_form_data(fd)
        mismatch = [w for w in warnings if 'mismatch' in w.get('msg', '')]
        self.assertGreater(len(mismatch), 0)


class WrongDbTypeValidationTests(TestCase):

    def test_postgres_vars_without_postgres_container(self):
        """POSTGRES_HOST gesetzt, aber nur MariaDB im Pod → Error."""
        fd = _make_form([
            _c('db', 'docker.io/mariadb:11',
               'MARIADB_USER=u\nMARIADB_PASSWORD=p\nMARIADB_DATABASE=d\nMARIADB_ROOT_PASSWORD=r'),
            _c('nc', 'docker.io/nextcloud:latest',
               'POSTGRES_HOST=127.0.0.1\nPOSTGRES_USER=nc\nPOSTGRES_PASSWORD=p\nPOSTGRES_DB=nc'),
        ])
        warnings = validate_form_data(fd)
        error_msgs = [w['msg'] for w in warnings if w['level'] == 'error']
        self.assertTrue(any('POSTGRES_HOST' in m and 'nc' in m for m in error_msgs),
                        f'Expected POSTGRES_HOST error, got: {error_msgs}')

    def test_mysql_vars_without_mysql_container(self):
        """MYSQL_HOST gesetzt, aber nur PostgreSQL im Pod → Error."""
        fd = _make_form([
            _c('db', 'docker.io/postgres:16',
               'POSTGRES_USER=u\nPOSTGRES_PASSWORD=p\nPOSTGRES_DB=d'),
            _c('app', 'docker.io/wordpress:latest',
               'MYSQL_HOST=127.0.0.1\nMYSQL_USER=wp\nMYSQL_PASSWORD=p\nMYSQL_DATABASE=wp'),
        ])
        warnings = validate_form_data(fd)
        error_msgs = [w['msg'] for w in warnings if w['level'] == 'error']
        self.assertTrue(any('MYSQL_HOST' in m and 'app' in m for m in error_msgs),
                        f'Expected MYSQL_HOST error, got: {error_msgs}')

    def test_no_false_positive_correct_db(self):
        """POSTGRES_HOST + Postgres-Container → kein falscher-DB-Typ-Error."""
        fd = _make_form([
            _c('db', 'docker.io/postgres:16',
               'POSTGRES_USER=app\nPOSTGRES_PASSWORD=p\nPOSTGRES_DB=app'),
            _c('nc', 'docker.io/nextcloud:latest',
               'POSTGRES_HOST=127.0.0.1\nPOSTGRES_USER=app\nPOSTGRES_PASSWORD=p\nPOSTGRES_DB=app'),
        ])
        warnings = validate_form_data(fd)
        db_type_errors = [w for w in warnings if w.get('hint') == 'POSTGRES_HOST' and w['level'] == 'error']
        self.assertEqual(db_type_errors, [])

    def test_remote_host_no_warning(self):
        """POSTGRES_HOST auf externem Server → kein Warning."""
        fd = _make_form([
            _c('app', 'docker.io/nextcloud:latest',
               'POSTGRES_HOST=db.example.com\nPOSTGRES_USER=nc\nPOSTGRES_DB=nc'),
        ])
        warnings = validate_form_data(fd)
        db_type_errors = [w for w in warnings if w.get('hint') == 'POSTGRES_HOST']
        self.assertEqual(db_type_errors, [])
