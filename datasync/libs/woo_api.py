from time import time
from urllib.parse import urlencode

import cloudscraper
from requests.auth import HTTPBasicAuth
from woocommerce import API
from woocommerce.oauth import OAuth


class WooCloudFlareApi(API):
	def __init__(self, url, consumer_key, consumer_secret, **kwargs):
		super().__init__(url, consumer_key, consumer_secret, **kwargs)
		self.user_agent = None


	def __get_url(self, endpoint):
		""" Get URL for requests """
		url = self.url
		api = "wc-api"

		if url.endswith("/") is False:
			url = f"{url}/"

		if self.wp_api:
			api = "wp-json"

		return f"{url}{api}/{self.version}/{endpoint}"


	def __get_oauth_url(self, url, method, **kwargs):
		""" Generate oAuth1.0a URL """
		oauth = OAuth(
			url = url,
			consumer_key = self.consumer_key,
			consumer_secret = self.consumer_secret,
			version = self.version,
			method = method,
			oauth_timestamp = kwargs.get("oauth_timestamp", int(time()))
		)

		return oauth.get_oauth_url()


	def _API__request(self, method, endpoint, data, params = None, **kwargs):
		""" Do requests """
		if params is None:
			params = {}
		url = self.__get_url(endpoint)
		auth = None
		headers = {
			# "user-agent": f"{self.user_agent}",
			# "accept": "application/json"
		}

		if self.is_ssl is True and self.query_string_auth is False:
			auth = HTTPBasicAuth(self.consumer_key, self.consumer_secret)
		elif self.is_ssl is True and self.query_string_auth is True:
			params.update({
				"consumer_key": self.consumer_key,
				"consumer_secret": self.consumer_secret
			})
		else:
			encoded_params = urlencode(params)
			url = f"{url}?{encoded_params}"
			url = self.__get_oauth_url(url, method, **kwargs)

		scraper = cloudscraper.create_scraper()
		return scraper.perform_request(
			method = method,
			url = url,
			verify = self.verify_ssl,
			auth = auth,
			params = params,
			json = data,
			timeout = self.timeout,
			headers = headers,
			**kwargs
		)
