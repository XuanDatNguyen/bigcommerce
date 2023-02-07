import mysql.connector
from mysql.connector import errorcode

from datasync.libs.utils import *


class Mysql:
    CONST_MSG_ERR = 'Could not connect database.'

    def __init__(self):
        self._db = None
        self._conn = None
        self._cursor = None
        self._db_host = ''
        self._db_port = ''
        self._db_username = ''
        self._db_password = ''
        self._db_name = ''
        self._config_db_name = ''
        self._db_prefix = ''
        self.set_config()

    def default_config(self):
        default_config = dict()
        default_config['db_host'] = ''
        default_config['db_username'] = ''
        default_config['db_password'] = ''
        default_config['db_name'] = ''
        default_config['db_prefix'] = ''
        default_config['db_port'] = ''
        return default_config

    def get_db_host(self):
        if self._db_host:
            return self._db_host
        default_config = self.default_config()
        return default_config['db_host']

    def log(self, msg, query='', type_error='mysql'):
        msg_log = query + ": " + msg if query else msg
        log(msg_log, type_error=type_error)

    def get_db_username(self):
        if self._db_username:
            return self._db_username
        default_config = self.default_config()
        return default_config['db_username']

    def get_db_password(self):
        if self._db_password:
            return self._db_password
        default_config = self.default_config()
        return default_config['db_password']

    def get_db_name(self):
        if self._db_name:
            return self._db_name
        default_config = self.default_config()
        return default_config['db_name']

    def get_db_prefix(self):
        if self._db_prefix:
            return self._db_prefix
        default_config = self.default_config()
        return default_config['db_prefix']

    def set_db_host(self, host=''):
        self._db_host = host
        return self

    def set_username(self, username=''):
        self._db_username = username
        return self

    def set_db_password(self, password=''):
        self._db_password = password
        return self

    def set_db_name(self, name=''):
        self._db_name = name
        return self

    def set_db_prefix(self, prefix=''):
        self._db_prefix = prefix
        return self

    def set_db_port(self, port=3306):
        self._db_port = port
        return self

    def get_db_port(self):
        if self._db_port:
            return self._db_port
        default_config = self.default_config()
        return default_config['db_port']

    def set_config(self):
        config_file = os.path.join(get_pub_path(), '..', 'etc', 'local.ini')
        if not os.path.isfile(config_file):
            return False
        config = configparser.ConfigParser()
        config.read(config_file)
        self.set_db_host(config['db']['db_host']).set_username(config['db']['db_username']).set_db_password(
            config['db']['db_password']).set_db_prefix(config['db']['db_prefix']).set_db_name(config['db']['db_name'])
        try:
            self.set_db_port(config['db']['db_port'])
        except:
            pass

        return self

    def get_config(self):
        config = dict()
        config['host'] = self.get_db_host()
        config['user'] = self.get_db_username()
        config['password'] = self.get_db_password()
        config['database'] = self.get_db_name()
        config['raise_on_warnings'] = True
        config['collation'] = 'utf8_general_ci'
        config['charset'] = 'utf8'
        config['use_unicode'] = True
        # config['auth_plugin'] = 'mysql_native_password'
        db_port = self.get_db_port()
        if to_int(db_port) and to_int(db_port) != 3306:
            config['port'] = db_port
        return config

    # TODO: CONNECT

    def connect(self):
        self.refresh_connect()

    def refresh_connect(self):
        self.close_connect()
        self._conn = self._create_connect()
        return self._conn

    def close_connect(self):
        if self._cursor:
            self._cursor.close()
        if self._conn:
            self._conn.close()
        self._cursor = None
        self._conn = None
        return True

    def _create_connect(self):
        config = self.get_config()
        try:
            cnx = mysql.connector.connect(**config)
            return cnx
        except mysql.connector.Error as err:
            if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
                self.log("Something is wrong with your user name or password")
            elif err.errno == errorcode.ER_BAD_DB_ERROR:
                self.log("Database does not exist: " + config['database'])
            else:
                self.log(err)
        return None

    def get_connect(self):
        if self._conn:
            return self._conn
        else:
            self._conn = self._create_connect()
        return self._conn

    def get_cursor(self):
        if self._cursor:
            return self._cursor
        conn = self.get_connect()
        if conn:
            self._cursor = conn.cursor(dictionary=True)
        return self._cursor

    def get_table_name(self, table):
        return self._db_prefix + table

    def escape(self, value):
        if value is None or value is False:
            return 'null'
        if value == '':
            return "''"
        if not value:
            return value
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            try:
                value = self.get_connect().converter.escape(value)
            except:
                value = value.replace('"', '\\"')
                value = value.replace("'", "\\'")
        return "'" + to_str(value) + "'"

    def dict_to_create_table_sql(self, dictionary):
        if not (isinstance(dictionary, dict)):
            return {'result': 'error', 'msg': "Data not exists."}

        table = dictionary['table']
        row_data = dictionary['rows']
        references_data = get_value_by_key_in_dict(
            dictionary, 'references', dict())
        unique_data = get_value_by_key_in_dict(dictionary, 'unique', dict())
        index_data = get_value_by_key_in_dict(dictionary, 'index', dict())
        rows = list()
        for row_name, construct in row_data.items():
            row = "`" + row_name + "` " + construct
            rows.append(row)

        references = list()
        for row_reference, data_reference in references_data.items():
            references.append("FOREIGN KEY (" + row_reference + ") REFERENCES " + self.get_table_name(
                data_reference['table']) + "(" + data_reference['row'] + ")")
        unique = list()
        if unique_data:
            for row_unique in unique_data:
                name = ''
                fields = list()
                for field in row_unique:
                    name += '-' + field.upper() if name else field.upper()
                    fields.append("`" + field + "`")
                str_unique = 'UNIQUE `' + name + '` ( '
                str_unique += ','.join(fields) + ' )'
                unique.append(str_unique)

        index = list()
        if index_data:
            for row_index in index_data:
                name = ''
                fields = list()
                for field in row_index:
                    name += '-' + field.upper() if name else field.upper()
                    fields.append("`" + field + "`")
                str_index = 'INDEX `' + name + '` ( '
                str_index += ','.join(fields) + ' )'
                index.append(str_index)

        table_name = self.get_table_name(table)
        query = "CREATE TABLE IF NOT EXISTS " + table_name + " ("
        query += ','.join(rows)
        if references:
            query += ","
            query += ','.join(references)
        if unique:
            query += ","
            query += ",".join(unique)
        if index:
            query += ","
            query += ",".join(index)
        query += ' )'
        return {'result': 'success', 'query': query}

    def dict_to_insert_condition(self, dictionary, allow_key=None):
        keys = dictionary.keys()
        data_key = list()
        data_value = list()
        if not allow_key:
            data_key = keys
            values = dictionary.values()
            for value in values:
                data_value.append(self.escape(value))
        else:
            for key in keys:
                if key in allow_key:
                    data_key.append(key)
                    value = dictionary[key]
                    if isinstance(value, int):
                        data_value.append(value)
                    else:
                        data_value.append(self.escape(value))
        if not data_key:
            return False
        data_value = list(map(lambda x: to_str(x), data_value))
        key_condition = '(`' + '`, `'.join(data_key) + '`)'
        value_condition = '(' + ', '.join(data_value) + ')'
        return key_condition + ' VALUES ' + value_condition

    def dict_to_where_condition(self, dictionary):
        if not dictionary:
            return '1 = 1'
        if isinstance(dictionary, str):
            return dictionary
        data = list()
        for key, value in dictionary.items():
            escape_value = self.escape(value)
            if escape_value == 'null':
                data.append("`" + to_str(key) + "` IS " + to_str(escape_value))
            else:
                data.append("`" + to_str(key) + "` = " + to_str(escape_value))
        condition = " AND ".join(data)
        return condition

    def dict_to_set_condition(self, dictionary):
        if not dictionary:
            return ''
        data = list()
        for key, value in dictionary.items():
            data.append("`" + to_str(key) + "` = " +
                        to_str(self.escape(value)))
        return ','.join(data)

    def list_to_in_condition(self, dictionary):
        if not dictionary:
            return "('null')"
        data = list(map(self.escape, dictionary))
        data = list(map(lambda x: to_str(x), data))
        return "(" + ",".join(data) + ")"

    # TODO: QUERY

    def select_raw(self, query, second_time=False):
        try:
            cursor = self.get_cursor()
            if not cursor:
                return response_error(self.CONST_MSG_ERR)
            cursor.execute(query)
            data = list()
            for row in cursor:
                data.append(row)
            return response_success(data)
        except mysql.connector.errors.OperationalError as e:
            if not second_time:
                self._conn = self.refresh_connect()
                return self.select_raw(query, True)
            else:
                return response_error(e.msg)
        except mysql.connector.Error as e:
            self.log(e.msg, query, 'database')
            return response_error(e.msg)

    def select_obj(self, table, where=None, select_field=None):
        table_name = self.get_table_name(table)
        cursor = self.get_cursor()
        if not cursor:
            return response_error(self.CONST_MSG_ERR)
        data_select = '*'
        if select_field and isinstance(select_field, list):
            data_select = ','.join(select_field)
        query = "SELECT " + data_select + " FROM `" + table_name + "`"
        if where:
            if isinstance(where, str):
                query += " WHERE " + where
            elif isinstance(where, dict):
                query += " WHERE " + self.dict_to_where_condition(where)
        return self.select_raw(query)

    def select_page(self, table, where=None, select_field=None, limit=None, offset=None, order_by=None):
        table_name = self.get_table_name(table)
        cursor = self.get_cursor()
        if not cursor:
            return response_error(self.CONST_MSG_ERR)
        data_select = '*'
        if select_field and isinstance(select_field, list):
            data_select = ','.join(select_field)
        query = "SELECT " + data_select + " FROM `" + table_name + "`"
        if where:
            if isinstance(where, str):
                query += " WHERE " + where
            elif isinstance(where, dict):
                query += " WHERE " + self.dict_to_where_condition(where)
        if order_by:
            query += " ORDER BY " + order_by

        if limit:
            query += " LIMIT " + to_str(limit)
        if offset and to_int(offset) > 0:
            query += " OFFSET " + to_str(offset)

        return self.select_raw(query)

    def count_table(self, table, where=None):
        table_name = self.get_table_name(table)
        cursor = self.get_cursor()
        if not cursor:
            return response_error(self.CONST_MSG_ERR)
        query = " SELECT COUNT(1) as count FROM " + table_name
        if where:
            if isinstance(where, str):
                query += " WHERE " + where
            elif isinstance(where, dict):
                query += " WHERE " + self.dict_to_where_condition(where)
        res = self.select_raw(query)
        if res['result'] == 'success' and to_len(res['data']) > 0:
            return res['data'][0]['count']
        return 0

    def select_max(self, table, select_field, where=None):
        table_name = self.get_table_name(table)
        cursor = self.get_cursor()
        if not cursor:
            return response_error(self.CONST_MSG_ERR)
        query = " SELECT max(`" + select_field + "`) as max FROM " + table_name
        if where:
            if isinstance(where, str):
                query += " WHERE " + where
            elif isinstance(where, dict):
                query += " WHERE " + self.dict_to_where_condition(where)
        res = self.select_raw(query)
        if res['result'] == 'success' and to_len(res['data']) > 0:
            return res['data'][0]['max']
        return 0

    def insert_raw(self, query, insert_id=False, second_time=False):
        cursor = self.get_cursor()
        if not cursor:
            return response_error()
        try:
            cursor.execute(query)
            self._conn.commit()
            data = True
            if insert_id:
                data = cursor.lastrowid
            return response_success(data)
        except mysql.connector.errors.OperationalError as e:
            if not second_time:
                self._conn = self.refresh_connect()
                return self.insert_raw(query, insert_id, True)
            else:
                return response_error(e.msg)
        except mysql.connector.Error as e:

            self.log(e.msg, query, 'database')
            return response_error(e.msg)

    def insert_obj(self, table, data, insert_id=False):
        table_name = self.get_table_name(table)
        data_condition = self.dict_to_insert_condition(data)
        query = "INSERT INTO `" + table_name + "` " + data_condition
        return self.insert_raw(query, insert_id)

    def insert_multiple_obj(self, table, data):
        table_name = self.get_table_name(table)
        fields = list()
        values = list()
        for row in data:
            if not fields:
                fields = list(row.keys())
            value = list()
            for field in fields:
                value.append(row[field])
            # value = list(map(lambda x: to_str(x), value))
            values.append(tuple(value))
        data_value = list(map(lambda x: to_str(x), fields))
        key_condition = '(`' + '`, `'.join(data_value) + '`)'
        data_value = list()
        for field in fields:
            data_value.append('%s')
        value_condition = '(' + ', '.join(data_value) + ')'
        data_condition = key_condition + ' VALUES ' + value_condition
        query = "INSERT INTO `" + table_name + "` " + data_condition
        return self.insert_multiple_raw(query, values)

    def insert_multiple_raw(self, query, params, second_time=False):
        cursor = self.get_cursor()
        if not cursor:
            return response_error()
        try:
            cursor.executemany(query, params)
            self._conn.commit()
            data = True
            return response_success(data)
        except mysql.connector.errors.OperationalError as e:
            if not second_time:
                self._conn = self.refresh_connect()
                return self.insert_raw(query, params, True)
            else:
                return response_error(e.msg)
        except mysql.connector.Error as e:

            self.log(e.msg, query, 'database')
            return response_error(e.msg)

    def update_obj(self, table, data, where=None):
        table_name = self.get_table_name(table)
        set_condition = self.dict_to_set_condition(data)
        if not set_condition:
            return response_error()
        query = "UPDATE `" + table_name + "` SET " + set_condition
        if where:
            if isinstance(where, str):
                query += " WHERE " + where
            elif isinstance(where, dict):
                query += " WHERE " + self.dict_to_where_condition(where)
            else:
                pass
        return self.query_raw(query)

    def query_raw(self, query, second_time=False):
        cursor = self.get_cursor()
        if not cursor:
            return response_error()
        try:
            cursor.execute(query)
            self._conn.commit()
            # self._cursor.close()
            return response_success()
        except mysql.connector.errors.OperationalError as e:
            if not second_time:
                self._conn = self.refresh_connect()
                return self.query_raw(query, True)
            else:
                return response_error(e.msg)
        except mysql.connector.Error as e:
            if e.errno == errorcode.ER_TABLE_EXISTS_ERROR:
                return response_success()
            self.log(e.msg, query, 'database')
            return response_error(e.msg)

    def delete_obj(self, table, where=None):
        cursor = self.get_cursor()
        if not cursor:
            return response_error()
        table_name = self.get_table_name(table)
        query = "DELETE FROM `" + table_name + "`"
        if where:
            if isinstance(where, str):
                query += " WHERE " + where
            elif isinstance(where, dict):
                query += " WHERE " + self.dict_to_where_condition(where)
            else:
                pass
        return self.query_raw(query)

    def execute_scripts_from_file(self, file_path):
        cursor = self.get_cursor()
        if not cursor:
            return response_error()
        fd = open(file_path, 'r')
        sql_file = fd.read()
        fd.close()
        sql_commands = sql_file.split(';')

        for command in sql_commands:
            try:
                if command.strip() != '':
                    cursor.execute(command)
            except mysql.connector.Error as e:

                self.log(e.msg, '', 'database')
        return response_success()
