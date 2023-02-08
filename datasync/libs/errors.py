from datasync.libs.messages import Messages


class Errors:
	URL_INVALID = 2601
	URL_NOT_FOUND = 2602
	URL_IS_LOCALHOST = 2603

	CHANNEL_NOT_CREATE = 2501
	CHANNEL_EXIST = 2502

	STATE_NOT_CREATE = 2401

	ACTION_INVALID = 2301

	EXCEPTION = 2201
	EXCEPTION_IMPORT = 2202

	PROCESS_NOT_CREATE = 2101
	RECONNECT_DIFFERENT_SITE = 2102

	SHOPIFY_SCOPE = 2701  # Thiếu scope
	SHOPIFY_VARIANT_LIMIT = 2702  # full variant
	SHOPIFY_API_INVALID = 2703  # full variant
	SHOPIFY_GET_PRODUCT_FAIL = 2704
	SHOPIFY_PRODUCT_NO_VARIANT = 2705
	SHOPIFY_URL_INVALID = 2706
	SHOPIFY_GET_ORDER_FAIL = 2707
	SHOPIFY_ORDER_NO_ITEM = 2708
	SHOPIFY_SCOPE_INVALID = 2709
	SHOPIFY_ORDER_ITEM_NOT_LINK = 2710

	WIX_API_INVALID = 3103
	WIX_GET_PRODUCT_FAIL = 3104
	WIX_IMPORT_VARIANT_FAIL = 3105

	WOOCOMMERCE_INVALID_SKU = 2902
	WOOCOMMERCE_ID_OR_SKU_REQUIRED = 2903
	WOOCOMMERCE_INVALID_URL = 2904
	WOOCOMMERCE_API_PERMISSION = 2905
	WOOCOMMERCE_ERROR_500 = 2906
	WOOCOMMERCE_ERROR_FIREWALL = 2907
	WOOCOMMERCE_CONNECT_FAIL = 2908
	WOOCOMMERCE_MOD_REWRITE = 2909
	WOOCOMMERCE_ERROR_503 = 2910

	PRODUCT_DATA_INVALID = 2801
	PRODUCT_NOT_EXIST = 2802
	PRODUCT_NOT_EXPORT = 2803
	PRODUCT_NOT_CREATE = 2804
	PRODUCT_RATE_LIMIT = 2805

	CATEGORY_PARENT_NOT_CREATE = 2901

	CART_INFO_INVALID = 1101
	CART_NOT_CREATE_MIGRATION = 1102

	BIGCOMMERCE_API_PATH_INVALID = 1201
	BIGCOMMERCE_API_INVALID = 1202
	BIGCOMMERCE_GET_PRODUCT_FAIL = 1203
	BIGCOMMERCE_GET_ODER_FAIL = 1204

	ETSY_API_INVALID = 1301
	ETSY_FAIL_API = 1303
	ETSY_GET_PRODUCT_FAIL = 1304
	ETSY_RATE_LIMIT = 1305
	ETSY_VARIANT_LIMIT = 1306
	ETSY_INVENTORY_VARIANT_FAIL = 1307
	ETSY_SHIPPING_ZIP_CODE = 1308

	FACEBOOK_INFO_INVALID = 1501
	FACEBOOK_FAIL_API = 1503

	AMAZON_REQUEST_TIMEOUT = 1801
	AMAZON_API_INVALID = 1802
	AMAZON_PUSH_PRODUCT_ERROR = 1803
	AMAZON_GET_PRODUCT_ERROR = 1804
	AMAZON_GET_ORDER_ERROR = 1805
	AMAZON_ACCOUNT_INACTIVE = 1806
	AMAZON_INVALID_ASIN = 99022

	GOOGLE_REQUEST_TIMEOUT = 1901
	GOOGLE_API_INVALID = 1902
	GOOGLE_REFRESH_ACCESS_TOKEN_ERROR = 1903
	GOOGLE_SKU_EMPTY = 1904
	GOOGLE_MERCHANT_ID_INVALID = 1905

	EBAY_API_INVALID = 2001
	EBAY_NOT_RESPONSE = 2002
	EBAY_CATEGORY_REQUIRED = 2003

	CHANNEL_NAME_REQUIRED = 1401
	SETUP_DATA_INVALID = 1402

	PROCESS_PRODUCT_NOT_EXIST = 1601
	PROCESS_ORDER_NOT_CREATE = 1602
	PROCESS_INVENTORY_NOT_CREATE = 1603

	SCHEDULER_NOT_EXIST = 1701
	SCHEDULER_PROCESS_ID_NOT_MATCH = 1702

	TEMPLATE_NOT_FOUND = 1901

	CM_NOT_CONNECT = 2001

	ORDER_RATE_LIMIT = 3001
	ORDER_NO_PRODUCT = 3002

	SQUARESPACE_API_INVALID = 3200
	SQUARESPACE_NOT_STORE_PAGE = 3201

	CSV_FILE_NOT_MATCH = 3300
	CSV_FILE_MISSING_FIELD = 3301


	WISH_API_INVALID = 3401
	WISH_OPTION_VARIANT_TOO_MUCH = 3402
	WISH_OPTION_VARIANT = 3403
	WISH_OPTION_VARIANT_INVALID = 3405
	WISH_DESCRIPTION_REQUIRED = 3406
	def __init__(self):
		self.error_msg = self.error_message()


	def error_message(self):
		return {
			self.URL_IS_LOCALHOST: "Unfortunately, you can\'t perform connect from localhost! You should upload your site to a live server for the app to work.",
			self.RECONNECT_DIFFERENT_SITE: "Please reconnect to the correct site you connected to.",
			self.WOOCOMMERCE_ERROR_500: 'we received an "Internal Server Error" error returned from your site. This prevented the connection from our system to your website. Please contact us for more solutions.',
			self.WOOCOMMERCE_ERROR_503: "The WooCommerce server is temporarily unable to service your request due to maintenance downtime or capacity problems. Please try again later or contact us for more solutions.",
			self.SHOPIFY_SCOPE_INVALID: "Please enter api password with sufficient permissions: read_products,write_products,write_inventory,read_locations",
			self.SHOPIFY_ORDER_ITEM_NOT_LINK: "The order has an unlinked product. Please check again.",
			self.EBAY_NOT_RESPONSE: "no response from ebay. Please try again later",
			self.EBAY_CATEGORY_REQUIRED: "Primary Category is required. Please select a category before trying again",
			self.WOOCOMMERCE_INVALID_URL: "The url you just entered doesn't seem to be woocommerce. Please check again",
			self.GOOGLE_SKU_EMPTY: 'sku is empty.',
			self.AMAZON_ACCOUNT_INACTIVE: 'Due to limited amazon account activity, your ability to create listings has been disabled.',
			self.SHOPIFY_ORDER_NO_ITEM: 'Order no products',
			self.ETSY_INVENTORY_VARIANT_FAIL: 'At least One product must have a quantity greater than 0',
			self.WOOCOMMERCE_API_PERMISSION: 'Api Invalid. The Api you provide must have read/write permission',
			self.URL_INVALID: 'Url invalid. Please enter the correct url',
			self.CHANNEL_NOT_CREATE: 'This channel failed to create',
			self.CHANNEL_EXIST: 'You have already connected that channel',
			self.STATE_NOT_CREATE: 'State failed to create',
			self.ACTION_INVALID: 'Invalid action',
			self.EXCEPTION: 'There was an error',
			self.PROCESS_NOT_CREATE: 'Process failed to create',
			self.SHOPIFY_SCOPE: 'SHOPIFY_SCOPE',
			self.SHOPIFY_VARIANT_LIMIT: 'SHOPIFY_VARIANT_LIMIT',
			self.SHOPIFY_API_INVALID: 'SHOPIFY_API_INVALID',
			self.SHOPIFY_GET_PRODUCT_FAIL: 'SHOPIFY_GET_PRODUCT_FAIL',
			self.SHOPIFY_PRODUCT_NO_VARIANT: 'SHOPIFY_PRODUCT_NO_VARIANT',
			self.PRODUCT_DATA_INVALID: 'PRODUCT_DATA_INVALID',
			self.PRODUCT_NOT_EXIST: 'PRODUCT_NOT_EXIST',
			self.CATEGORY_PARENT_NOT_CREATE: 'CATEGORY_PARENT_NOT_CREATE',
			self.CART_INFO_INVALID: 'CART_INFO_INVALID',
			self.BIGCOMMERCE_API_PATH_INVALID: 'BIGCOMMERCE_API_PATH_INVALID',
			self.BIGCOMMERCE_API_INVALID: 'BIGCOMMERCE_API_INVALID',
			self.BIGCOMMERCE_GET_PRODUCT_FAIL: 'BIGCOMMERCE_GET_PRODUCT_FAIL',
			self.CART_NOT_CREATE_MIGRATION: 'CART_NOT_CREATE_MIGRATION',
			self.CHANNEL_NAME_REQUIRED: 'Channel name required',
			self.SETUP_DATA_INVALID: 'SETUP_DATA_INVALID',
			self.SQUARESPACE_API_INVALID: 'SQUARESPACE_API_INVALID',
			self.PRODUCT_NOT_EXPORT: 'PRODUCT_NOT_EXPORT',
			self.PRODUCT_NOT_CREATE: 'PRODUCT_NOT_CREATE',
			self.SHOPIFY_URL_INVALID: 'Please enter the correct url (https://storeid.myshopify.com)',
			self.ETSY_SHIPPING_ZIP_CODE: 'Invalid ZIP/Postal Code. Please go to Store Manager > Settings > Shipping Settings > click on Shipping Label Options at the top and edit your selected shipping profile.',
			self.ETSY_FAIL_API: 'Error returned from Etsy',
			self.ETSY_API_INVALID: 'Error returned from info channel Etsy',
			self.ETSY_GET_PRODUCT_FAIL: 'ETSY_GET_PRODUCT_FAIL',
			self.ETSY_RATE_LIMIT: "Error returned from Etsy: Has exceeded the limit of calling request to api. Please wait another 30 minutes",
			self.FACEBOOK_INFO_INVALID: 'Error returned from info channel Facebook',
			self.FACEBOOK_FAIL_API: 'Error returned from Facebook',
			self.PROCESS_PRODUCT_NOT_EXIST: 'PROCESS_PRODUCT_NOT_EXIST',
			self.SCHEDULER_NOT_EXIST: 'SCHEDULER_NOT_EXIST',
			self.SCHEDULER_PROCESS_ID_NOT_MATCH: 'SCHEDULER_PROCESS_ID_NOT_MATCH',
			self.SHOPIFY_GET_ORDER_FAIL: 'SHOPIFY_GET_ORDER_FAIL',
			self.WOOCOMMERCE_INVALID_SKU: 'Your sku already exists on woocommerce. Please import products from woocommerce to LitC and link them, or edit the sku to continue importing.',
			self.WOOCOMMERCE_ID_OR_SKU_REQUIRED: 'Product ID or SKU is required',
			self.PROCESS_INVENTORY_NOT_CREATE: 'PROCESS_INVENTORY_NOT_CREATE',
			self.AMAZON_REQUEST_TIMEOUT: 'AMAZON_REQUEST_TIMEOUT',
			self.AMAZON_API_INVALID: 'AMAZON_API_INVALID',
			self.AMAZON_PUSH_PRODUCT_ERROR: 'AMAZON_PUSH_PRODUCT_ERROR',
			self.AMAZON_GET_PRODUCT_ERROR: 'AMAZON_GET_PRODUCT_ERROR',
			self.AMAZON_GET_ORDER_ERROR: 'AMAZON_GET_ORDER_ERROR',
			self.AMAZON_INVALID_ASIN: 'AMAZON_INVALID_ASIN',
			self.GOOGLE_REQUEST_TIMEOUT: 'GOOGLE_REQUEST_TIMEOUT',
			self.GOOGLE_API_INVALID: 'GOOGLE_API_INVALID',
			self.GOOGLE_REFRESH_ACCESS_TOKEN_ERROR: 'GOOGLE_REFRESH_ACCESS_TOKEN_ERROR',
			self.EBAY_API_INVALID: 'Error returned from Ebay',
			self.CM_NOT_CONNECT: "Can't connect to cm server",
			self.TEMPLATE_NOT_FOUND: "TEMPLATE_NOT_FOUND",
			self.ORDER_RATE_LIMIT: Messages.ORDER_RATE_LIMIT_TITLE,
			self.PRODUCT_RATE_LIMIT: Messages.PRODUCT_RATE_LIMIT_TITLE,
			self.ORDER_NO_PRODUCT: 'ORDER_NO_PRODUCT',
			self.URL_NOT_FOUND: 'URL_NOT_FOUND',
			self.EXCEPTION_IMPORT: 'There was an error while importing. Please try again later',
			self.WIX_IMPORT_VARIANT_FAIL: 'WIX_IMPORT_VARIANT_FAIL',
			self.ETSY_VARIANT_LIMIT: 'Etsy only allows products with up to 70 variants. Please hide some variants before importing.',
			self.SQUARESPACE_NOT_STORE_PAGE: 'Your store does not have a store page enabled. Please enable at least one store page.',
			self.WOOCOMMERCE_ERROR_FIREWALL: 'We detect this website is under {} Firewall. Please temporarily turn off the firewall for the api to work properly, or contact us for more solutions.',
			self.WOOCOMMERCE_CONNECT_FAIL: 'We are unable to connect to your website. Please check again or contact us for more solution.',
			self.CSV_FILE_NOT_MATCH: 'The file you provided does not match the structure of the sample file.',
			self.CSV_FILE_MISSING_FIELD: 'The file you provided is missing a field: {}',
			self.WOOCOMMERCE_MOD_REWRITE: 'We are unable to connect to your api. Please enable mod_rewrite before trying again',
			self.GOOGLE_MERCHANT_ID_INVALID: 'Merchant id you provided is incorrect. Please check again',
			self.WISH_API_INVALID: 'WISH_API_INVALID',
			self.WIX_API_INVALID: 'WIX_API_INVALID',
			self.WISH_OPTION_VARIANT_TOO_MUCH: 'Your product has too many options for variation. Wish only accepts variations with 2 options: size, color.',
			self.WISH_OPTION_VARIANT: 'Your product is missing the Size or Color option. Wish only accepts variations with 2 options: size, color.',
			self.WISH_OPTION_VARIANT_INVALID: '{} attributes do not match.. Wish only accepts variations with 2 options: size, color.',
			self.WISH_DESCRIPTION_REQUIRED: 'Description is required',
		}


	def get_msg_error(self, error_code, default = None):
		if not default:
			default = error_code
		if not error_code:
			return ''
		return self.error_msg.get(int(error_code), default)
