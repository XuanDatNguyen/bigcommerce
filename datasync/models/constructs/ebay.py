from typing import List

from datasync.models.constructs.base import ConstructBase


class EbayCategorySimple(ConstructBase):
	def __init__(self, **kwargs):
		self.category_id = ''
		self.category_name = ""
		super().__init__(**kwargs)


class EbayCategoryConditionSimple(ConstructBase):
	def __init__(self, **kwargs):
		self.condition_id = ''
		self.condition_name = ''
		super().__init__(**kwargs)


class EbayCategoryCondition(ConstructBase):
	def __init__(self, **kwargs):
		self.new = ''
		self.used = ''
		self.reconditioned = ''
		self.value = EbayCategoryConditionSimple()
		super().__init__(**kwargs)


class EbayCategorySpecifics(ConstructBase):
	def __init__(self, **kwargs):
		self.name = ''
		self.mapping = ''
		self.override = ''
		self.value = ''
		super().__init__(**kwargs)


class EbayCategory(ConstructBase):
	specifics: List[EbayCategorySpecifics]


	def __init__(self, **kwargs):
		self.primary_category = EbayCategorySimple()
		self.secondary_category = EbayCategorySimple()
		self.store_category_1 = EbayCategorySimple()
		self.store_category_2 = EbayCategorySimple()
		self.condition = EbayCategoryCondition()
		self.listing_type = ''
		self.duration = ''
		self.specifics = list()

		super().__init__(**kwargs)


class PaymentItemLocation(ConstructBase):
	def __init__(self, **kwargs):
		self.address = ''
		self.country = ""
		self.postal_code = ""
		super().__init__(**kwargs)


class PaymentSalesTax(ConstructBase):
	def __init__(self, **kwargs):
		self.status = self.DISABLE
		self.state = ""
		self.value = ""
		self.shipping_include_tax = ""
		super().__init__(**kwargs)


class BaseReturnPolicy(ConstructBase):
	def __init__(self, **kwargs):
		self.status = self.DISABLE
		self.within = ""
		self.paid_by = ""
		self.replace_or_exchange = self.DISABLE
		super().__init__(**kwargs)


class PaymentReturnPolicy(ConstructBase):
	def __init__(self, **kwargs):
		self.status = self.DISABLE
		self.domestic_return = BaseReturnPolicy()
		self.international_return = BaseReturnPolicy()
		super().__init__(**kwargs)


class MaximumRequirementFeebackBlock(ConstructBase):
	def __init__(self, **kwargs):
		self.score = 0
		super().__init__(**kwargs)


class MaximumRequirementBlock(ConstructBase):
	def __init__(self, **kwargs):
		self.status = self.DISABLE
		self.count = 0
		self.feedback = 0
		super().__init__(**kwargs)


class MaximumUnpaidStrikeBlock(ConstructBase):
	def __init__(self, **kwargs):
		self.status = self.DISABLE
		self.count = 0
		self.period = 0
		super().__init__(**kwargs)


class BuyerRequirement(ConstructBase):
	def __init__(self, **kwargs):
		self.status = self.DISABLE
		self.maximum_unpaid_item_strikes = MaximumUnpaidStrikeBlock()
		self.ship_to_registration_country = self.DISABLE
		self.maximum_item_requirements = MaximumRequirementBlock()
		super().__init__(**kwargs)


class PaymentTemplate(ConstructBase):
	def __init__(self, **kwargs):
		self.paypal_email = ""
		self.payment_instructions = ""
		self.auto_pay = self.DISABLE
		self.handling_time = 0
		self.item_location = PaymentItemLocation()
		self.sales_tax = PaymentSalesTax()
		self.ebay_tax_table = self.DISABLE
		self.return_policy = PaymentReturnPolicy()
		self.buyer_requirements = BuyerRequirement()
		super().__init__(**kwargs)


class EbayRateTable(ConstructBase):
	def __init__(self, **kwargs):
		self.status = self.DISABLE
		self.rate_table_id = ''
		self.rate_table_name = ""
		super().__init__(**kwargs)


class DomesticShippingService(ConstructBase):
	def __init__(self, **kwargs):
		self.shipping_service = ''
		self.shipping_service_id = ''
		self.free_shipping = 0
		self.cost = 0
		self.additional_cost = 0
		super().__init__(**kwargs)


class Location(ConstructBase):
	def __init__(self, **kwargs):
		self.code = ''
		self.name = ''
		super().__init__(**kwargs)


class InternationalShippingService(ConstructBase):
	ship_to_location: List[str]
	additional_ship_to_locations: List[str]


	def __init__(self, **kwargs):
		self.shipping_service = ''
		self.shipping_service_id = ''
		self.ship_to_location = list()
		self.additional_ship_to_locations = list()
		self.cost = 0
		self.additional_cost = 0
		super().__init__(**kwargs)


class ShippingWeight(ConstructBase):
	def __init__(self, **kwargs):
		self.major = 0
		self.minor = 0
		super().__init__(**kwargs)


class DomesticShipping(ConstructBase):
	calculated_options_attributes: List[DomesticShippingService]
	flat_options_attributes: List[DomesticShippingService]


	def __init__(self, **kwargs):
		self.shipment_type = ''
		self.promotional_shipping_discount = False
		self.weight = ShippingWeight()
		self.rate_table = EbayRateTable()
		self.originating_postal_code = ""
		self.shipping_package = ''
		self.packaging_handling_costs = 0
		self.calculated_options_attributes = list()
		self.flat_options_attributes = list()
		super().__init__(**kwargs)


class ExcludedLocation(ConstructBase):
	locations: List[str]


	def __init__(self, **kwargs):
		self.status = self.DISABLE
		self.locations = list()
		super().__init__(**kwargs)


class InternationalShipping(ConstructBase):
	calculated_options_attributes: List[InternationalShippingService]
	flat_options_attributes: List[InternationalShippingService]
	additional_locations: List[str]


	def __init__(self, **kwargs):
		self.status = self.DISABLE
		self.shipment_type = ''
		self.promotional_shipping_discount = False
		self.originating_postal_code = ""
		self.packaging_handling_costs = 0
		self.rate_table = EbayRateTable()
		self.calculated_options_attributes = list()
		self.flat_options_attributes = list()
		self.additional_locations = list()
		super().__init__(**kwargs)


class ShippingTemplate(ConstructBase):
	def __init__(self, **kwargs):
		self.domestic_shipping = DomesticShipping()
		self.international_shipping = InternationalShipping()
		self.global_shipping = False
		self.excluded_locations = ExcludedLocation()
		super().__init__(**kwargs)


class SimplePriceBestOfferTemplate(ConstructBase):
	def __init__(self, **kwargs):
		self.status = self.DISABLE
		self.direction = 'increment'
		self.modifier = 'percent'
		self.value = 0
		self.price = 0
		super().__init__(**kwargs)


class PriceBestOfferTemplate(ConstructBase):
	def __init__(self, **kwargs):
		self.status = self.DISABLE

		self.accept_price = SimplePriceBestOfferTemplate()
		self.decline_price = SimplePriceBestOfferTemplate()
		super().__init__(**kwargs)


class CustomPriceTemplate(ConstructBase):
	def __init__(self, **kwargs):
		self.status = self.DISABLE
		self.value = 0
		super().__init__(**kwargs)


class AdjustmentPriceTemplate(ConstructBase):
	def __init__(self, **kwargs):
		self.direction = 'increment'
		self.modifier = 'percent'
		self.value = 0
		super().__init__(**kwargs)


class SimplePriceTemplate(ConstructBase):
	def __init__(self, **kwargs):
		self.adjustment = AdjustmentPriceTemplate()
		self.custom_price = CustomPriceTemplate()
		super().__init__(**kwargs)


class AuctionSimplePriceTemplate(SimplePriceTemplate):
	def __init__(self, **kwargs):
		self.status = self.DISABLE
		self.price = 0
		super().__init__(**kwargs)


class FixedPriceTemplate(ConstructBase):
	def __init__(self, **kwargs):
		self.buy_it_now_price = SimplePriceTemplate()
		self.best_offer = PriceBestOfferTemplate()
		super().__init__(**kwargs)


class AuctionPriceTemplate(ConstructBase):
	def __init__(self, **kwargs):
		self.start_price = AuctionSimplePriceTemplate()
		self.buy_it_now_price = AuctionSimplePriceTemplate()
		self.reserve_price = AuctionSimplePriceTemplate()
		super().__init__(**kwargs)


class PriceTemplate(ConstructBase):
	def __init__(self, **kwargs):
		self.fixed_price = FixedPriceTemplate()
		self.auction_price = AuctionPriceTemplate()
		super().__init__(**kwargs)
