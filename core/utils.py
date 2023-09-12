from .models import Order

def handle_checkout_session(session):
    user = session["metadata"]["user"]
    print(user)
    order = Order.objects.get(user=user, ordered=False)
    order.ordered = True
    order.save()
    print(order.user)