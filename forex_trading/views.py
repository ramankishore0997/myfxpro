# views.py
from django.urls import reverse_lazy
from django.views.generic import TemplateView, FormView
from django.contrib.auth import login, authenticate
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
import requests
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib import messages
from .forms import CustomUserCreationForm, CustomUserLoginForm, WithdrawForm, ProfileUpdateForm
from .models import DepositOption, WithdrawalRequest, Transaction, DepositRequest, Trade, CrptoId
import json
from django.shortcuts import render
from django.views import View
from django.views.generic.edit import CreateView
from django.utils import timezone
from datetime import timedelta


class HomePage(TemplateView):
    template_name = 'landingpage/index.html'


class SignupView(FormView):
    template_name = 'signup.html'
    form_class = CustomUserCreationForm
    success_url = reverse_lazy('dashboard')

    def form_valid(self, form):
        user = form.save()
        login(self.request, user)
        return super().form_valid(form)

    def form_invalid(self, form):
        # Optionally, you can add a message here for form submission failure
        messages.error(self.request, "Please correct the errors below.")
        return super().form_invalid(form)


class LoginView(FormView):
    template_name = 'login.html'
    form_class = CustomUserLoginForm
    success_url = reverse_lazy('dashboard')

    def form_valid(self, form):
        email = form.cleaned_data.get("email")
        password = form.cleaned_data.get("password")
        user = authenticate(self.request, email=email, password=password)
        if user is not None:
            login(self.request, user)
            return super().form_valid(form)
        else:
            messages.error(self.request, "Invalid email or password.")
            return self.form_invalid(form)


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'dashboard.html'


class DepositView(View):
    def get(self, request):
        deposit_options = DepositOption.objects.all()
        context = {
            'crypto_address': CrptoId.objects.all().first().cry_id,
            'deposit_options': deposit_options
        }
        return render(request, 'deposit.html', context)


class WithdrawView(CreateView):
    model = WithdrawalRequest
    form_class = WithdrawForm
    template_name = 'withdraw.html'
    success_url = reverse_lazy('dashboard')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user  # Pass user to the form
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Retrieve the most recent withdrawal request for the user
        latest_request = WithdrawalRequest.objects.filter(
            user=self.request.user
        ).order_by('-request_date').first()

        # Retrieve all withdrawal requests for the user, ordered by date
        context['withdrawal_requests'] = WithdrawalRequest.objects.filter(
            user=self.request.user
        ).order_by('-request_date')

        # Determine if the user can withdraw based on the latest request's status
        if latest_request and not latest_request.is_processed and not latest_request.is_rejected:
            # If there is a pending, non-rejected request, disable withdrawal
            context['existing_request'] = latest_request
            context['can_withdraw'] = False
            context['estimated_processing_time'] = latest_request.request_date + timedelta(days=5)
        else:
            # Enable withdrawal if there are no pending or non-rejected requests
            context['can_withdraw'] = True

        return context

    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)


@login_required
def profile_view(request):
    if request.method == 'POST':
        form = ProfileUpdateForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            return redirect('profile')  # Redirect to the profile page after saving
    else:
        form = ProfileUpdateForm(instance=request.user)

    return render(request, 'profile.html', {'form': form})


@login_required
@csrf_exempt
def deposit_request_view(request):
    TELEGRAM_API_URL = "https://api.telegram.org/bot7704560273:AAHbrHwF6d6ykhQvppXlAwQlI7sixrRxp_E/sendMessage"
    CHAT_ID = "-1002267045390"

    def send_telegram_message(message):
        data = {
            'chat_id': CHAT_ID,
            'text': message,
        }
        response = requests.post(TELEGRAM_API_URL, data=data)
        return response

    if request.method == 'POST':
        data = json.loads(request.body)
        method = data.get('method')
        amount = data.get('amount', 1000)  # Example default amount, modify as needed
        upi_id = data.get('upi_id')
        message = f"New Deposit Request:\nMethod: {method}\nUPI ID: {upi_id}\nAmount: ₹{amount}\nEMAIL: {request.user.email}"

        if method == 'UPI':
            upi_id = data.get('upi_id')
            deposit_request = DepositRequest.objects.create(user=request.user, method=method, upi_id=upi_id, amount=amount)
        elif method == 'USDT':
            crypto_address = data.get('crypto_address')
            deposit_request = DepositRequest.objects.create(user=request.user, method=method, crypto_address=crypto_address, amount=amount)

        send_telegram_message(message)

        deposit_request.save()
        return JsonResponse({'message': 'Deposit request submitted successfully.', 'method':method , 'success':True})

    return JsonResponse({'message': 'Invalid request'}, status=400)


class UserTradesView(TemplateView):
    template_name = 'user_trades.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get the current date and time
        now = timezone.now()

        # Get the 'date_filter' parameter from the request
        date_filter = self.request.GET.get('date_filter', 'today')

        # Default: Show all trades if no filter is selected
        if date_filter == 'today':
            # Filter trades that occurred today
            start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
            trades = Trade.objects.filter(user=self.request.user, trade_time__gte=start_of_day)

        elif date_filter == 'yesterday':
            # Filter trades that occurred yesterday
            start_of_yesterday = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            end_of_yesterday = (now - timedelta(days=1)).replace(hour=23, minute=59, second=59, microsecond=999999)
            trades = Trade.objects.filter(user=self.request.user, trade_time__range=[start_of_yesterday, end_of_yesterday])

        elif date_filter == '7_days':
            # Filter trades that occurred in the last 7 days
            start_of_7_days_ago = now - timedelta(days=7)
            trades = Trade.objects.filter(user=self.request.user, trade_time__gte=start_of_7_days_ago)

        else:
            # Default: Show today's trades if no filter is selected
            start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
            trades = Trade.objects.filter(user=self.request.user, trade_time__gte=start_of_day)

        # Calculate the total profit from the filtered trades
        total_profit = sum(trade.profit for trade in trades)
        context['total_profit'] = total_profit

        context['trades'] = trades
        context['date_filter'] = date_filter  # To pass selected filter value to the template
        return context
