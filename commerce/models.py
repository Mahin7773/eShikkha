from django.conf import settings
from django.db import models
from django.db.models import Q
from django.urls import reverse


class Cart(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='cart')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Cart of {self.user}'


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    course = models.ForeignKey('courses.Course', on_delete=models.CASCADE, related_name='cart_items')
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-added_at']
        constraints = [models.UniqueConstraint(fields=['cart', 'course'], name='unique_cart_course')]


class Order(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending payment'
        PAID = 'paid', 'Paid'
        FAILED = 'failed', 'Payment failed'
        CANCELLED = 'cancelled', 'Cancelled'
        REFUNDED = 'refunded', 'Refunded'

    order_number = models.CharField(max_length=32, unique=True)
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='orders')
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING, db_index=True)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    discount_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='USD')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.CheckConstraint(condition=Q(total__gte=0), name='order_total_non_negative'),
        ]

    def __str__(self):
        return self.order_number

    def get_absolute_url(self):
        return reverse('commerce:order_detail', args=[self.order_number])

    @property
    def is_payable(self):
        return self.status in (self.Status.PENDING, self.Status.FAILED)

    @property
    def status_tone(self):
        return {'pending': 'info', 'paid': 'success', 'failed': 'danger',
                'cancelled': 'neutral', 'refunded': 'warning'}[self.status]


class OrderItem(models.Model):
    # prices are copied here when the order is created

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    course = models.ForeignKey('courses.Course', on_delete=models.PROTECT, related_name='order_items')
    instructor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+')
    list_price = models.DecimalField(max_digits=8, decimal_places=2)
    discount_amount = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    price_paid = models.DecimalField(max_digits=8, decimal_places=2)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['order', 'course'], name='unique_order_course')]

    def __str__(self):
        return f'{self.course} @ {self.price_paid}'


class PaymentTransaction(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        SUCCESSFUL = 'successful', 'Successful'
        FAILED = 'failed', 'Failed'
        CANCELLED = 'cancelled', 'Cancelled'
        REFUNDED = 'refunded', 'Refunded'

    class Outcome(models.TextChoices):
        SUCCESS = 'success', 'Approve payment'
        DECLINE = 'decline', 'Decline (insufficient funds)'
        CANCEL = 'cancel', 'Cancel at gateway'

    GATEWAY_NAME = 'eShikkha Sandbox (simulated)'

    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name='transactions')
    transaction_id = models.CharField(max_length=40, unique=True)
    gateway = models.CharField(max_length=60, default=GATEWAY_NAME)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING, db_index=True)
    simulated_outcome = models.CharField(max_length=10, choices=Outcome.choices)
    message = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            # an order can only be paid once
            models.UniqueConstraint(fields=['order'], condition=Q(status='successful'),
                                    name='one_successful_transaction_per_order'),
        ]

    def __str__(self):
        return self.transaction_id

    @property
    def status_tone(self):
        return {'pending': 'info', 'successful': 'success', 'failed': 'danger',
                'cancelled': 'neutral', 'refunded': 'warning'}[self.status]


class InstructorEarning(models.Model):
    """Instructor's share of a sale (simulated, not a real payout)."""

    class Status(models.TextChoices):
        RECORDED = 'recorded', 'Recorded (simulated)'
        REVERSED = 'reversed', 'Reversed (refund)'

    order_item = models.OneToOneField(OrderItem, on_delete=models.PROTECT, related_name='earning')
    instructor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='earnings')
    course = models.ForeignKey('courses.Course', on_delete=models.PROTECT, related_name='earnings')
    gross_amount = models.DecimalField(max_digits=10, decimal_places=2)
    fee_percent = models.DecimalField(max_digits=5, decimal_places=2)
    platform_fee = models.DecimalField(max_digits=10, decimal_places=2)
    net_amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.RECORDED)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['instructor', 'status'])]
