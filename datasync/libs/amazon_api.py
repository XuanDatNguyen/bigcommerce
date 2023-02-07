import base64
import os
import time

import requests
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from sp_api.api import Catalog, Feeds, Reports, Orders, ListingsItems
from sp_api.base import ApiResponse, sp_endpoint, fill_query_params

from datasync.libs.utils import obj_to_list, to_str, log


class AmazonApiResponse(ApiResponse):
	def __init__(self, payload = None, errors = None, pagination = None, headers = None, nextToken = None, **kwargs):
		super().__init__(payload, errors, pagination, headers, nextToken, **kwargs)
		self.status_code = kwargs.get('status_code')


class AmazonClientMixin(object):
	def log(self, msg, log_type = 'exceptions'):
		prefix = "user/" + to_str(self._user_id)
		if self._channel_id:
			prefix = os.path.join('channel', to_str(self._channel_id))
			if self._process_type:
				prefix += '/' + self._process_type
		elif self._sync_id:
			prefix = os.path.join('processes', to_str(self._sync_id))

		log(msg, prefix, log_type)


	def log_request_error(self, url, log_type = 'request', **kwargs):
		msg_log = 'Url: ' + to_str(url)
		for log_key, log_value in kwargs.items():
			msg_log += '\n{}: {}'.format(to_str(log_key).capitalize(), to_str(log_value))
		self.log(msg_log, log_type)


	@staticmethod
	def _check_response(res) -> ApiResponse:
		return AmazonApiResponse(**res.json(), headers = res.headers, status_code = res.status_code)


	def _request(self, path: str, *, data: dict = None, params: dict = None, headers = None,
	             add_marketplace = True) -> ApiResponse:
		response = super()._request(path = path, data = data, params = params, headers = headers, add_marketplace = add_marketplace)
		if response.status_code > 204:
			self.log_request_error(path, data = data, params = params, response = response.errors)
		retry = 0
		while response.status_code == 429 and retry <= 5:
			retry += 1
			time.sleep(retry * 5)
			self.log(f"sleep {retry * 5}s", "sleep")
			response = super()._request(path = path, data = data, params = params, headers = headers, add_marketplace = add_marketplace)
			if response.status_code > 204:
				self.log_request_error(path, data = data, params = params, response = response.errors)
		return response


class AmazonCatalog(AmazonClientMixin, Catalog):
	def __init__(self, **kwargs):
		self._channel_id = kwargs.get('channel_id')
		self._sync_id = kwargs.get('sync_id')
		self._user_id = kwargs.get('user_id')
		self._process_type = kwargs.get('process_type')
		fields = ['channel_id', 'sync_id', 'user_id', 'process_type']
		for field in fields:
			if kwargs.get(field):
				del kwargs[field]
		super().__init__(**kwargs)


	@sp_endpoint('/catalog/2020-12-01/items/{}')
	def get_item_variant(self, asin, **kwargs) -> ApiResponse:
		"""
		get_item_variant(self, asin: str, **kwargs) -> ApiResponse
		Returns a specified item and its attributes.

		**Usage Plan:**

		======================================  ==============
		Rate (requests per second)               Burst
		======================================  ==============
		1                                       1
		======================================  ==============

		For more information, see "Usage Plans and Rate Limits" in the Selling Partner API documentation.

		Args:
			asin: str
			key MarketplaceIds: str
			**kwargs:

		Returns:
			GetCatalogItemResponse:
		"""
		return self._request(fill_query_params(kwargs.pop('path'), asin), params = kwargs)


class AmazonFeed(AmazonClientMixin, Feeds):
	def __init__(self, **kwargs):
		self._channel_id = kwargs.get('channel_id')
		self._sync_id = kwargs.get('sync_id')
		self._user_id = kwargs.get('user_id')
		self._process_type = kwargs.get('process_type')
		fields = ['channel_id', 'sync_id', 'user_id', 'process_type']
		for field in fields:
			if kwargs.get(field):
				del kwargs[field]
		super().__init__(**kwargs)


	@sp_endpoint('/feeds/2020-09-04/feeds/{}', method = 'DELETE')
	def cancel_feed(self, feed_id: str, **kwargs) -> ApiResponse:
		return self._request(fill_query_params(kwargs.pop('path'), feed_id))


	@sp_endpoint('/feeds/2020-09-04/feeds', method = 'GET')
	def get_feeds(self, feed_types = None, marketplace_ids = None, **kwargs) -> ApiResponse:
		params = {

		}
		if feed_types:
			feed_types = obj_to_list(feed_types)
			params['feedTypes'] = feed_types
		if marketplace_ids:
			params['marketplaceIds'] = obj_to_list(marketplace_ids)
		if kwargs:
			params.update(kwargs)
		return self._request(kwargs.get('path'), params = params)


	@sp_endpoint('/feeds/2020-09-04/documents', method = 'POST')
	def create_feed_document(self, content, content_type = 'text/tsv', **kwargs) -> ApiResponse:
		"""
		create_feed_document(self, content: Content File, content_type='text/tsv', **kwargs) -> ApiResponse
		Creates a feed document for the feed type that you specify.
		This method also encrypts and uploads the file you specify.

		**Usage Plan:**

		======================================  ==============
		Rate (requests per second)               Burst
		======================================  ==============
		0.0083                                  15
		======================================  ==============

		For more information, see "Usage Plans and Rate Limits" in the Selling Partner API documentation.

		Args:
			content: str
			content_type: str
			**kwargs:

		Returns:
			CreateFeedDocumentResponse:

		"""
		data = {
			'contentType': kwargs.get('contentType', content_type)
		}
		from sp_api.base.exceptions import SellingApiException
		response = self._request(kwargs.get('path'), data = {**data, **kwargs})
		if not response or not response.payload or not response.payload.get('encryptionDetails') or not response.payload.get('encryptionDetails').get('key') or not response.payload.get('encryptionDetails').get('initializationVector'):
			self.log(response, 'create_feed')
		upload = requests.put(
			response.payload.get('url'),
			data = self.encrypt_aes(content,
			                        response.payload.get('encryptionDetails').get('key'),
			                        response.payload.get('encryptionDetails').get('initializationVector')
			                        ),
			headers = {'Content-Type': content_type}
		)
		if 200 <= upload.status_code < 300:
			return response
		raise SellingApiException(upload.headers)


	def encrypt_aes(self, text, key, iv):
		key = base64.b64decode(key)
		iv = base64.b64decode(iv)
		aes = AES.new(key, AES.MODE_CBC, iv)
		try:
			return aes.encrypt(pad(bytes(text, encoding = 'utf-8'), 16))
		except Exception:
			return aes.encrypt(pad(bytes(text, encoding = 'iso-8859-1'), 16))


class AmazonReport(AmazonClientMixin, Reports):
	def __init__(self, **kwargs):
		self._channel_id = kwargs.get('channel_id')
		self._sync_id = kwargs.get('sync_id')
		self._user_id = kwargs.get('user_id')
		self._process_type = kwargs.get('process_type')
		fields = ['channel_id', 'sync_id', 'user_id', 'process_type']
		for field in fields:
			if kwargs.get(field):
				del kwargs[field]
		super().__init__(**kwargs)


	@sp_endpoint('/reports/2020-09-04/reports/{}', method = 'DELETE')
	def cancel_report(self, report_id: str, **kwargs) -> ApiResponse:
		return self._request(fill_query_params(kwargs.pop('path'), report_id))


	def decrypt_report_document(self, url, initialization_vector, key, encryption_standard, payload):
		encoding = ['utf-8', 'windows-1252', 'iso-8859-1']
		decrypt_data = super(AmazonReport, self).decrypt_report_document(url, initialization_vector, key, encryption_standard, payload)
		for row in encoding:
			try:
				decrypt_data_encode = decrypt_data.encode('iso-8859-1').decode(row)
				return decrypt_data_encode
			except Exception:
				continue
		return decrypt_data


class AmazonOrder(AmazonClientMixin, Orders):
	def __init__(self, **kwargs):
		self._channel_id = kwargs.get('channel_id')
		self._sync_id = kwargs.get('sync_id')
		self._user_id = kwargs.get('user_id')
		self._process_type = kwargs.get('process_type')
		fields = ['channel_id', 'sync_id', 'user_id', 'process_type']
		for field in fields:
			if field in kwargs:
				del kwargs[field]
		super().__init__(**kwargs)


	@sp_endpoint('/orders/v0/orders', method = 'GET')
	def get_orders(self, created_after = None, marketplace_ids = None, **kwargs) -> ApiResponse:
		params = {}
		if created_after:
			params['CreatedAfter'] = created_after
		if marketplace_ids:
			params['MarketplaceIds'] = obj_to_list(marketplace_ids)
		if kwargs:
			params.update(kwargs)
		return self._request(kwargs.get('path'), params = params)


class AmazonListingItems(AmazonClientMixin, ListingsItems):
	def __init__(self, **kwargs):
		self._channel_id = kwargs.get('channel_id')
		self._sync_id = kwargs.get('sync_id')
		self._user_id = kwargs.get('user_id')
		self._process_type = kwargs.get('process_type')
		fields = ['channel_id', 'sync_id', 'user_id', 'process_type']
		for field in fields:
			if kwargs.get(field):
				del kwargs[field]
		super().__init__(**kwargs)


	@sp_endpoint('/listings/2021-08-01/items/{}/{}', method = 'GET')
	def get_listings_item(self, seller_id, sku, **kwargs) -> ApiResponse:

		return self._request(fill_query_params(kwargs.pop('path'), seller_id, sku), params = kwargs)
