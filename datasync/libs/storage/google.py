import os
import urllib.request

from google.cloud import storage

from datasync.libs.utils import get_config_ini, log_traceback, get_root_path, to_bool


class StorageGoogle:
	SECTION_CONFIG = 'storage'


	def __init__(self):
		super().__init__()
		self._bucket_name = ''
		self._domain_name = get_config_ini(self.SECTION_CONFIG, 'domain')
		self._bucket_name = get_config_ini(self.SECTION_CONFIG, 'bucket_name')
		self._config_file = get_config_ini(self.SECTION_CONFIG, 'config_file')
		self._storage_client = ''
		self._bucket = ''
		self._blob = ''


	def allow_upload(self):
		return to_bool(get_config_ini('local', 'allow_storage'))


	def get_blob(self, destination_blob_name):
		if not self._bucket:
			self.init_bucket()
		return self.create_blob(destination_blob_name)


	def init_bucket(self):
		self._storage_client = storage.Client.from_service_account_json(os.path.join(get_root_path(), 'etc', self._config_file))
		self._bucket = self._storage_client.bucket(self._bucket_name)


	def create_blob(self, destination_blob_name):
		return self._bucket.blob(destination_blob_name)


	def upload_file_from_url(self, url, destination_name):
		if not self.allow_upload():
			return url
		try:
			file = urllib.request.urlopen(url)
			info = file.info()
			return self.upload_file_from_raw(file.read(), info.get_content_type(), destination_name)
		except Exception as e:
			log_traceback('storage')
			return None


	def upload_file_from_local(self, local_file, destination_name):
		try:
			blob = self.get_blob(destination_name)
			blob.upload_from_filename(local_file)
			return self._domain_name.strip('/') + "/" + destination_name.strip('/')
		except Exception as e:
			log_traceback('storage')
			return None


	def upload_file_from_raw(self, raw_data, content_type, destination_name):
		try:
			blob = self.get_blob(destination_name)
			blob.upload_from_string(raw_data, content_type = content_type)
			return self._domain_name.strip('/') + "/" + destination_name.strip('/')
		except Exception as e:
			log_traceback('storage')
			return None


	def delete_file(self, image_url):
		destination_name = str(image_url).replace(self._domain_name, '').strip('/')
		try:
			blob = self.get_blob(destination_name)
			blob.delete()
		except:
			pass
		return True


class ImageStorageGoogle(StorageGoogle):
	SECTION_CONFIG = 'image_storage'


class FileStorageGoogle(StorageGoogle):
	SECTION_CONFIG = 'file_storage'
