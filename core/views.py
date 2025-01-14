from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render, get_object_or_404
from django.views.generic import ListView, DetailView, View
from django.shortcuts import redirect
from django.utils import timezone

from core.utils import handle_checkout_session
from .forms import CheckoutForm, CouponForm, EditProfileForm, RefundForm
from .models import Item, OrderItem, Order, BillingAddress, Payment, Coupon, Refund, Category, ShippingCost
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render_to_response
from django.views.decorators.csrf import csrf_exempt

# Create your views here.
import random
import string
import stripe
stripe.api_key = settings.STRIPE_SECRET_KEY


def create_ref_code():
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=20))

@login_required
def profile(request):
    user = request.user
    orders = Order.objects.filter(user=user, ordered=True)
    if request.method == 'POST':
        form = EditProfileForm(request.POST)
        if form.is_valid():
            # Procesa y actualiza los datos del usuario aquí
            user.username = form.cleaned_data['username']
            user.email = form.cleaned_data['email']
    else:
        form = EditProfileForm(initial={'username': user.username, 'email': user.email})

    return render(request, 'profile.html', {'form': form, 'orders': orders})

class PaymentView(View):
    def get(self, *args, **kwargs):
        # order
        order = Order.objects.get(user=self.request.user, ordered=False)
        if order.billing_address:
            context = {
                'order': order,
                'DISPLAY_COUPON_FORM': False,
                'cart': order,
                'shipping_cost': ShippingCost.get_instance(),
            }
            return render(self.request, "payment.html", context)
        else:
            messages.warning(
                self.request, "No has añadido una dirección de facturación")
            return redirect("core:checkout")

    def post(self, *args, **kwargs):
        order = Order.objects.get(user=self.request.user, ordered=False)
        token = self.request.POST.get('stripeToken')
        amount = int(order.get_total() * 100) # cents

        try:
            charge = stripe.Charge.create(
                amount=amount,  # cents
                currency="eur",
                source=token,
                metadata={'user': self.request.user.id}
            )
            # create the payment
            payment = Payment()
            payment.stripe_charge_id = charge['id']
            payment.user = self.request.user
            payment.amount = order.get_total()
            payment.save()

            # assign the payment to the order
            order.payment = payment
            # TODO : assign ref code
            order.ref_code = create_ref_code()
            order.save()

            messages.success(self.request, "Pago realizado correctamente.")
            return redirect("/")

        except stripe.error.CardError as e:
            # Since it's a decline, stripe.error.CardError will be caught
            body = e.json_body
            err = body.get('error', {})
            messages.error(self.request, f"{err.get('message')}")
            return redirect("/")

        except stripe.error.RateLimitError as e:
            # Too many requests made to the API too quickly
            messages.error(self.request, "RateLimitError")
            return redirect("/")

        except stripe.error.InvalidRequestError as e:
            # Invalid parameters were supplied to Stripe's API
            print(e)
            messages.error(self.request, "Invalid parameters")
            return redirect("/")

        except stripe.error.AuthenticationError as e:
            # Authentication with Stripe's API failed
            # (maybe you changed API keys recently)
            messages.error(self.request, "Not Authentication")
            return redirect("/")

        except stripe.error.APIConnectionError as e:
            # Network communication with Stripe failed
            messages.error(self.request, "Network Error")
            return redirect("/")

        except stripe.error.StripeError as e:
            # Display a very generic error to the user, and maybe send
            # yourself an email
            messages.error(self.request, "Something went wrong")
            return redirect("/")

        except Exception as e:
            # send an email to ourselves
            messages.error(self.request, "Serious Error occured")
            return redirect("/")


class HomeView(ListView):
    template_name = "index.html"
    queryset = Item.objects.filter(is_active=True)
    context_object_name = 'items'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.user.is_authenticated:
            try:
                order = Order.objects.get(user=self.request.user, ordered=False)
                context['cart'] = order
            except ObjectDoesNotExist:
                pass
        return context


class OrderSummaryView(LoginRequiredMixin, View):
    def get(self, *args, **kwargs):
        try:
            order = Order.objects.get(user=self.request.user, ordered=False) 
            context = {
                'cart': order,
                'shipping_cost': ShippingCost.get_instance()
            }
            return render(self.request, 'order_summary.html', context)
        except ObjectDoesNotExist:
            messages.error(self.request, "No tienes ningún pedido abierto")
            return redirect("/")


class ShopView(ListView):
    model = Item
    paginate_by = 6
    template_name = "shop.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.user.is_authenticated:
            try:
                order = Order.objects.get(user=self.request.user, ordered=False)
                context['cart'] = order
            except ObjectDoesNotExist:
                pass
        return context


class ItemDetailView(DetailView):
    model = Item
    template_name = "product-detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.user.is_authenticated:
            try:
                order = Order.objects.get(user=self.request.user, ordered=False)
                context['cart'] = order
            except ObjectDoesNotExist:
                pass
        return context


# class CategoryView(DetailView):
#     model = Category
#     template_name = "category.html"

class CategoryView(View):
    def get(self, *args, **kwargs):
        category = Category.objects.get(slug=self.kwargs['slug'])
        item = Item.objects.filter(category=category, is_active=True)
        if self.request.user.is_authenticated:
            try:
                order = Order.objects.get(user=self.request.user, ordered=False)
                context = {
                'object_list': item,
                'category_title': category,
                'category_description': category.description,
                'category_image': category.image,
                'cart': order
            }
            except ObjectDoesNotExist:
                context = {
                'object_list': item,
                'category_title': category,
                'category_description': category.description,
                'category_image': category.image
            }
            
        else:
            context = {
                'object_list': item,
                'category_title': category,
                'category_description': category.description,
                'category_image': category.image
            }
        return render(self.request, "category.html", context)


class CheckoutView(View):
    def get(self, *args, **kwargs):
        try:
            order = Order.objects.get(user=self.request.user, ordered=False)
            form = CheckoutForm()
            context = {
                'form': form,
                'couponform': CouponForm(),
                'cart': order,
                'DISPLAY_COUPON_FORM': True,
                'shipping_cost': ShippingCost.get_instance()
            }
            return render(self.request, "checkout.html", context)

        except ObjectDoesNotExist:
            messages.info(self.request, "No tienes ningún pedido abierto")
            return redirect("core:checkout")

    def post(self, *args, **kwargs):
        form = CheckoutForm(self.request.POST or None)
        try:
            order = Order.objects.get(user=self.request.user, ordered=False)
            print(self.request.POST)
            if form.is_valid():
                street_address = form.cleaned_data.get('street_address')
                apartment_address = form.cleaned_data.get('apartment_address')
                country = form.cleaned_data.get('country')
                city = form.cleaned_data.get('city')
                zip = form.cleaned_data.get('zip')
                # add functionality for these fields
                same_shipping_address = form.cleaned_data.get(
                     'same_shipping_address')
                # save_info = form.cleaned_data.get('save_info')
                # payment_option = form.cleaned_data.get('payment_option')
                shipping_address = BillingAddress(
                    user=self.request.user,
                    street_address=street_address,
                    apartment_address=apartment_address,
                    country=country,
                    city=city,
                    zip=zip,
                    address_type='S'
                )
                
                if same_shipping_address:
                    billing_address = BillingAddress(
                        user=self.request.user,
                        street_address=street_address,
                        apartment_address=apartment_address,
                        country=country,
                        city=city,
                        zip=zip,
                        address_type='B'
                    )
                else:
                    street_address_billing = form.cleaned_data.get('street_address_billing')
                    apartment_address_billing = form.cleaned_data.get('apartment_address_billing')
                    country_billing = form.cleaned_data.get('country_billing')
                    city_billing = form.cleaned_data.get('city_billing')
                    zip_billing = form.cleaned_data.get('zip_billing')
                    # Set the attributes of the form to the billing address
                    billing_address = BillingAddress(
                        user=self.request.user,
                        street_address=street_address_billing,
                        apartment_address=apartment_address_billing,
                        country=country_billing,
                        city=city_billing,
                        zip=zip_billing,
                        address_type='B'
                    )
                shipping_address.save()
                billing_address.save()
                order.shipping_address = shipping_address
                order.billing_address = billing_address
                order.save()

                # add redirect to the selected payment option
                return redirect('core:payment', payment_option='stripe')
                '''
                if payment_option == 'S':
                    return redirect('core:payment', payment_option='stripe')
                elif payment_option == 'P':
                    return redirect('core:payment', payment_option='paypal')
                
                else:
                    messages.warning(
                        self.request, "Invalid payment option select")
                    return redirect('core:checkout')
                '''
        except ObjectDoesNotExist:
            messages.error(self.request, "No tienes ningún pedido abierto")
            return redirect("core:order-summary")


# def home(request):
#     context = {
#         'items': Item.objects.all()
#     }
#     return render(request, "index.html", context)
#
#
# def products(request):
#     context = {
#         'items': Item.objects.all()
#     }
#     return render(request, "product-detail.html", context)
#
#
# def shop(request):
#     context = {
#         'items': Item.objects.all()
#     }
#     return render(request, "shop.html", context)


@login_required
def add_to_cart(request, slug, quantity=1):
    item = get_object_or_404(Item, slug=slug)
    order_item, created = OrderItem.objects.get_or_create(
        item=item,
        user=request.user,
        ordered=False
    )
    if request.POST.get("quantity", 1):
        quantity = int(request.POST.get("quantity", 1))
    order_qs = Order.objects.filter(user=request.user, ordered=False)
    if order_qs.exists():
        order = order_qs[0]
        if order.items.filter(item__slug=item.slug).exists():
            order_item.quantity += quantity
            order_item.save()
            messages.info(request, "La cantidad del producto añadido ha sido actualizado.")
            return redirect("core:order-summary")
        else:
            order_item.quantity = quantity
            order_item.save()
            order.items.add(order_item)
            messages.info(request, "El producto ha sido añadido a tu carrito.")
            return redirect("core:order-summary")
    else:
        ordered_date = timezone.now()
        order = Order.objects.create(
            user=request.user, ordered_date=ordered_date)
        order_item.quantity = quantity
        order_item.save()
        order.items.add(order_item)
        messages.info(request, "El producto ha sido añadido a tu carrito.")
    return redirect("core:order-summary")


@login_required
def remove_from_cart(request, slug):
    item = get_object_or_404(Item, slug=slug)
    order_qs = Order.objects.filter(
        user=request.user,
        ordered=False)
    if order_qs.exists():
        order = order_qs[0]
        # check if the order item is in the order
        if order.items.filter(item__slug=item.slug).exists():
            order_item = OrderItem.objects.filter(
                item=item,
                user=request.user,
                ordered=False
            )[0]
            order.items.remove(order_item)
            messages.info(request, "El producto ha sido eliminado de tu carrito.")
            return redirect("core:order-summary")
        else:
            # add a message saying the user dosent have an order
            messages.info(request, "El producto ha sido eliminado de tu carrito.")
            return redirect("core:product", slug=slug)
    else:
        # add a message saying the user dosent have an order
        messages.info(request, "No tienes ninguna orden activa.")
        return redirect("core:product", slug=slug)
    return redirect("core:product", slug=slug)


@csrf_exempt
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META['HTTP_STRIPE_SIGNATURE']
    event = None
    endpoint_secret = settings.STRIPE_ENDPOINT_SECRET
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, endpoint_secret
        )
    except ValueError as e:
        print(e)
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError as e:
        print(e)
        return HttpResponse(status=400)
    # Handle the checkout.session.completed event
    if event['type'] == 'charge.succeeded':
        session = event['data']['object']
        # Fulfill the purchase...
        handle_checkout_session(session)
    # Passed signature verification
    return HttpResponse(status=200)

@login_required
def remove_single_item_from_cart(request, slug):
    item = get_object_or_404(Item, slug=slug)
    order_qs = Order.objects.filter(
        user=request.user,
        ordered=False)
    if order_qs.exists():
        order = order_qs[0]
        # check if the order item is in the order
        if order.items.filter(item__slug=item.slug).exists():
            order_item = OrderItem.objects.filter(
                item=item,
                user=request.user,
                ordered=False
            )[0]
            if order_item.quantity > 1:
                order_item.quantity -= 1
                order_item.save()
            else:
                order.items.remove(order_item)
            messages.info(request, "La cantidad del producto ha sido actualizada.")
            return redirect("core:order-summary")
        else:
            # add a message saying the user dosent have an order
            messages.info(request, "El producto no estaba en tu carrito.")
            return redirect("core:product", slug=slug)
    else:
        # add a message saying the user dosent have an order
        messages.info(request, "No tienes ninguna orden activa.")
        return redirect("core:product", slug=slug)
    return redirect("core:product", slug=slug)


def get_coupon(request, code):
    try:
        coupon = Coupon.objects.get(code=code)
        return coupon
    except ObjectDoesNotExist:
        messages.info(request, "Este cupón no existe.")
        return redirect("core:checkout")


class AddCouponView(View):
    def post(self, *args, **kwargs):
        form = CouponForm(self.request.POST or None)
        if form.is_valid():
            try:
                code = form.cleaned_data.get('code')
                order = Order.objects.get(
                    user=self.request.user, ordered=False)
                order.coupon = get_coupon(self.request, code)
                order.save()
                messages.success(self.request, "Cupón aplicado con éxito.")
                return redirect("core:checkout")

            except ObjectDoesNotExist:
                messages.info(self.request, "No tienes ninguna orden activa.")
                return redirect("core:checkout")


class RequestRefundView(View):
    def get(self, *args, **kwargs):
        form = RefundForm()
        context = {
            'form': form
        }
        return render(self.request, "request_refund.html", context)

    def post(self, *args, **kwargs):
        form = RefundForm(self.request.POST)
        if form.is_valid():
            ref_code = form.cleaned_data.get('ref_code')
            message = form.cleaned_data.get('message')
            email = form.cleaned_data.get('email')
            # edit the order
            try:
                order = Order.objects.get(ref_code=ref_code)
                order.refund_requested = True
                order.save()

                # store the refund
                refund = Refund()
                refund.order = order
                refund.reason = message
                refund.email = email
                refund.save()

                messages.info(self.request, "Tu petición ha sido recibida.")
                return redirect("core:request-refund")

            except ObjectDoesNotExist:
                messages.info(self.request, "Esta orden no existe.")
                return redirect("core:request-refund")
