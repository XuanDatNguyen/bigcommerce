import re
import time
import urllib.parse

import pymongo
from bson import ObjectId

from datasync.libs.db.nosql import Nosql
from datasync.libs.utils import get_config_ini, to_int, to_str, to_object_id


class Mongo(Nosql):
    NAME = 'Mongo'
    ALLOW_WHERE_CONDITION = ('==', '>', '>=', '<', '<=', 'in', 'regex', 'like')

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._conn = None
        self._client = None
        self.__init__client__()
        self._database_name = kwargs.get(
            'database_name', get_config_ini('mongo', 'db_name'))

    def __init__client__(self):
        driver = get_config_ini('mongo', 'db_driver')
        password = self.encode_password(get_config_ini('mongo', 'db_password'))
        driver = driver.replace('<password>', password)
        self._client = pymongo.MongoClient(driver)

    def _get_client(self):
        return self._client

    def _create_connect(self, user_id):
        database_name = f"{get_config_ini('mongo', 'db_name')}_{user_id}"

        connect = getattr(self._get_client(), database_name)

        return connect

    def refresh_connect(self):
        self.close_connect()
        self._conn = self._create_connect()
        return self._conn

    def close_connect(self):
        self._client.close()
        self._client = None
        self._conn = None
        return True

    def get_col(self, user_id, collection_name):
        conn = self.get_conn(user_id)
        return getattr(conn, collection_name)

    def create_document(self, user_id, collection_name, _document_id=None, document_data=dict):
        collection = self.get_col(user_id, collection_name)
        document_data["id"] = self.document_auto_id()
        try:
            insert_id = collection.insert_one(document_data).inserted_id
        except Exception as e:
            self.log_traceback()
            insert_id = None
        return to_str(insert_id)

    def create_many_document(self, user_id, collection_name, document_data):
        collection = self.get_col(user_id, collection_name)
        for row in document_data:
            row['id'] = self.document_auto_id()
        try:
            insert_ids = collection.insert_many(document_data).inserted_ids
            insert_ids = list(map(lambda x: to_str(x), insert_ids))
        except Exception as e:
            self.log_traceback()
            insert_ids = ()
        return insert_ids

    def set_field(self, user_id, collection_name, _document_id, update_data=dict):
        if not update_data:
            return True
        collection = self.get_col(user_id, collection_name)
        query = {"_id": ObjectId(_document_id)}
        if update_data.get('_id'):
            del update_data['_id']
        document_update = {"$set": update_data}
        try:
            collection.update_one(query, document_update)
            return True
        except Exception as e:
            self.log_traceback()
            return False

    def update_raw_document(self, user_id, collection_name, _document_id, update_data=dict):
        if not update_data:
            return True
        collection = self.get_col(user_id, collection_name)
        query = {"_id": ObjectId(_document_id)}
        if update_data.get('_id'):
            del update_data['_id']
        document_update = update_data
        try:
            collection.update_one(query, document_update)
            return True
        except Exception as e:
            self.log_traceback()
            return False

    def update_raw_many_document(self, user_id, collection_name, where, update_data=dict):
        if not update_data:
            return True
        collection = self.get_col(user_id, collection_name)
        if update_data.get('_id'):
            del update_data['_id']
        document_update = update_data
        try:
            collection.update_many(where, document_update)
            return True
        except Exception as e:
            self.log_traceback()
            return False

    def update_document(self, user_id, collection_name, _document_id, update_data=dict):
        if not update_data:
            return True
        collection = self.get_col(user_id, collection_name)
        query = {"_id": ObjectId(_document_id)}
        if update_data.get('_id'):
            del update_data['_id']
        document_update = {"$set": update_data}
        try:
            collection.update_one(query, document_update)
            return True
        except Exception as e:
            self.log_traceback()
            return False

    def update_many_document(self, user_id, collection_name, where, update_data=dict):
        if not update_data:
            return True
        collection = self.get_col(user_id, collection_name)
        if update_data.get('_id'):
            del update_data['_id']
        document_update = {"$set": update_data}
        try:
            collection.update_many(where, document_update)
            return True
        except Exception as e:
            self.log_traceback()
            return False

    def get_document(self, user_id, collection_name, _document_id, select_fields=None):
        if not to_object_id(_document_id):
            return False
        collection = self.get_col(user_id, collection_name)
        query = {"_id": ObjectId(_document_id)}
        select = self.select_fields(select_fields)
        try:
            document = collection.find_one(query, select)
            if not document:
                return document
            return self.convert_data_before_return(dict(document))
        except Exception as e:
            self.log_traceback()
            return False

    def delete_document(self, user_id, collection_name, _document_id):
        collection = self.get_col(user_id, collection_name)
        query = {"_id": ObjectId(_document_id)}
        try:
            document = collection.find_one(query)
            collection.delete_many(query)
            return self.convert_data_before_return(dict(document if document else {}))
        except Exception:
            self.log_traceback()
            return False

    def delete_all(self, user_id, collection_name):
        collection = self.get_col(user_id, collection_name)
        query = {}
        try:
            collection.delete_many(query)
            return
        except Exception:
            self.log_traceback()
            return False

    def delete_many_document(self, user_id, collection_name, where):
        collection = self.get_col(user_id, collection_name)
        try:
            collection.delete_many(where)
            return
        except Exception:
            self.log_traceback()
            return False

    def get_all_collection(self, collection_name):
        pass

    def find_one(self, user_id, collection_name, where=list(), select_fields=None):
        collection_ref = self.get_col(user_id, collection_name)
        select = self.select_fields(select_fields)
        try:
            document = collection_ref.find_one(where, select)
            if not document:
                return document
            return self.convert_data_before_return(dict(document))
        except Exception as e:
            self.log_traceback()
            return False

    def find_all(self, user_id, collection_name, where=list(), order_by=None, sort=None, limit=None, pages=None, stream=False, select_fields=None):
        collection_ref = self.get_col(user_id, collection_name)
        try:
            select = self.select_fields(select_fields)
            docs = collection_ref.find(where, select)
            limit = to_int(limit)
            # if not limit:
            # 	limit = 20
            if limit:
                docs.limit(to_int(limit))
            pages = to_int(pages)
            if pages < 1:
                pages = 1
            if pages >= 2:
                docs.skip(limit * (pages - 1))
            if sort:
                sort_type = 1
                if to_str(sort)[0] == '-':
                    sort_type = -1
                    sort = to_str(sort)[1:]
                docs.sort(sort, sort_type)
                docs.collation({'locale': 'en'})
            docs = list(docs)
        except Exception as e:
            self.log_traceback()
            return False
        return self.convert_data_before_return(docs)

    def count_document(self, user_id, collection_name, where=list()):
        collection_ref = self.get_col(user_id, collection_name)
        return collection_ref.count_documents(where)

    def create_where_condition(self, field, value, condition="="):
        if field == '_id':
            if isinstance(value, str):
                value = ObjectId(value)
            if isinstance(value, (list, tuple)):
                value = tuple(map(lambda x: ObjectId(to_str(x)), value))
        if condition == 'exists':
            return {field: {
                    '$exists': value
                    }}
        if condition == 'range':
            where = {}
            if value[0]:
                where['$gt'] = value[0]
            if value[1]:
                where['$lt'] = value[1]
            return {field: where}
        if condition == 'erange':
            where = {}
            if value[0]:
                where['$gte'] = value[0]
            if value[1]:
                where['$lte'] = value[1]
            return {field: where}
        if condition == 'like':
            rgx = re.compile('.*{}.*'.format(value),
                             re.IGNORECASE)  # compile the regex
            return {field: rgx}
        if condition == '>':
            return {field: {'$gt': value}}
        if condition == '>=':
            return {field: {'$gte': value}}
        if condition == '<':
            return {field: {'$lt': value}}
        if condition == '<=':
            return {field: {'$lte': value}}
        if condition == 'in':
            return {field: {'$in': value}}
        if condition == 'nin':
            return {field: {'$nin': value}}
        if condition == '!=':
            return {field: {'$ne': value}}
        if condition == 'or':
            return {
                '$or': value
            }
        if condition == 'and':
            return {
                '$and': value
            }
        if condition == 'allElemMatch':
            elem_match = list()
            for row in value:
                elem_match.append(
                    {
                        "$elemMatch": row,
                    }
                )
            return {
                field: {
                    "$all": elem_match
                }
            }
        if condition == 'elmEq':
            return {
                field: {
                    "$eq": value
                }
            }
        if condition == 'elmMulTiEq':
            where = dict()
            elm_eq = list()
            for row in value:
                elm_eq.append(
                    {
                        field: {
                            "$eq": row
                        }
                    }
                )

            return {
                '$and': elm_eq
            }
        return {field: value}

    def next(self, object):
        try:
            value = object.__next__
            return value
        except StopIteration as e:
            return False
        except Exception:
            return False

    def convert_data_before_return(self, data):
        if isinstance(data, dict):
            if data.get('_id'):
                data['_id'] = str(data['_id'])
        if isinstance(data, list):
            for row in data:
                if row.get('_id'):
                    row['_id'] = str(row['_id'])
        return data

    def encode_password(self, password):
        if not password:
            return password
        scheme, netloc, path, qs, anchor = urllib.parse.urlsplit(password)
        path = urllib.parse.quote(path, '/%')
        qs = urllib.parse.quote_plus(qs, ':&=')
        return urllib.parse.urlunsplit((scheme, netloc, path, qs, anchor))

    def document_auto_id(self):
        time.sleep(0.1)
        return int(str(round(float(time.time()), 6)).replace('.', ''))

    def select_fields(self, select_fields):
        select = None
        if select_fields:
            if not isinstance(select_fields, (list, tuple)):
                select_fields = [select_fields]
            select = dict()
            for field in select_fields:
                select[field] = 1
        return select

    def select_aggregate(self, user_id, collection_name, query=list()):
        collection_ref = self.get_col(user_id, collection_name)
        try:
            docs = collection_ref.aggregate(query)
            docs = list(docs)
        except Exception as e:
            self.log_traceback()
            return False
        return self.convert_data_before_return(docs)

    def unset(self, user_id, collection_name, _document_id, fields):
        if not fields:
            return True
        collection_ref = self.get_col(user_id, collection_name)
        if not isinstance(fields, (list, tuple)):
            fields = [fields]
        query = {"_id": ObjectId(_document_id)}
        field_unset = dict()
        for field in fields:
            field_unset[field] = ''
        document_update = {"$unset": field_unset}
        try:
            collection_ref.update_one(query, document_update)
            return True
        except Exception as e:
            self.log_traceback()
            return False

    def unset_many(self, user_id, collection_name, where, fields):
        if not fields:
            return True
        collection_ref = self.get_col(user_id, collection_name)
        if not isinstance(fields, (list, tuple)):
            fields = [fields]
        field_unset = dict()
        for field in fields:
            field_unset[field] = ''
        document_update = {"$unset": field_unset}
        try:
            collection_ref.update(where, document_update, multi=True)
            return True
        except Exception as e:
            self.log_traceback()
            return False

    def create_index(self, user_id, collection_name, field, option=pymongo.ASCENDING, index_name=None):
        collection_ref = self.get_col(user_id, collection_name)
        kwargs = {}
        if index_name:
            kwargs['name'] = index_name
        collection_ref.create_index([(field, option)], **kwargs)

    def create_compound_index(self, user_id, collection_name, fields, option=pymongo.ASCENDING, index_name=None):
        collection_ref = self.get_col(user_id, collection_name)
        kwargs = {}
        if index_name:
            kwargs['name'] = index_name
        index = list()
        for field in fields:
            index.append((field, option))
        collection_ref.create_index(index, **kwargs)

    def create_text_index(self, user_id, collection_name, fields, index_name):
        collection_ref = self.get_col(user_id, collection_name)
        body = []
        kwargs = {}
        if index_name:
            kwargs['name'] = index_name
        fields = list(set(fields))
        for field in fields:
            body.append((field, 'text'))
        collection_ref.create_index(body, **kwargs)

    def list_index(self, user_id, collection_name):
        collection_ref = self.get_col(user_id, collection_name)
        return collection_ref.index_information()

    def drop_index(self, user_id, collection_name, index_name):
        collection_ref = self.get_col(user_id, collection_name)
        collection_ref.drop_index(index_name)
