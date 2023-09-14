from django.http import HttpResponseRedirect
from django.template.loader import render_to_string
from demo import settings
from .models import Order, ShippingCost
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.utils.html import strip_tags

def handle_checkout_session(session):
    user_id = session["metadata"]["user"]

    order = Order.objects.get(user=user_id, ordered=False)
    order.ordered = True
    order.save()
    user = User.objects.get(id=user_id)
    send_confirmed_order_mail(user.email, order)
    send_confirmed_order_to_owner(order)
    

def send_confirmed_order_mail(email, order):
    subject = 'Su pedido ha sido confirmado'
    #message = 'Tu pedido ha sido confirmado!\n \n  El pedido será enviado por correo y usted será informado de su seguimiento. \n \n Gracias por comprar en Arachis.'
    email_template = 'confirmation_mail.html'
    html_message = render_to_string(email_template, {'cart': order, 'shipping_cost': ShippingCost.get_instance().cost})
    from_email = settings.EMAIL_HOST_USER
    recipient_list = [email]

    # Crear una versión de texto sin formato del mensaje (para clientes de correo que no admiten HTML)
    plain_message = strip_tags(html_message)

    send_mail(subject, plain_message, from_email, recipient_list, html_message=html_message)

def send_confirmed_order_to_owner(order):
    subject = 'Pedido enviado en Arachis'
    email_template = 'confirmation_mail_owner.html'
    html_message = render_to_string(email_template, {'cart': order, 'shipping_cost': ShippingCost.get_instance().cost})
    from_email = settings.EMAIL_HOST_USER
    recipient_list = ["arachisresina@gmail.com"]

    # Crear una versión de texto sin formato del mensaje (para clientes de correo que no admiten HTML)
    plain_message = strip_tags(html_message)

    send_mail(subject, plain_message, from_email, recipient_list, html_message=html_message)
