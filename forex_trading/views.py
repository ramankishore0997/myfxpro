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
from .forms import CustomUserCreationForm, CustomUserLoginForm, WithdrawForm, ProfileUpdateForm,KYCForm
from .models import DepositOption, WithdrawalRequest, Transaction, DepositRequest, Trade, CrptoId, KYC, CustomUser
import json
from django.shortcuts import render
from django.views import View
from django.views.generic.edit import CreateView
from django.utils import timezone
from datetime import timedelta, datetime
from django.core.mail import send_mail, EmailMessage
from django.urls import reverse
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes
from django.contrib.sites.shortcuts import get_current_site
from django.template.loader import render_to_string
from django.contrib.auth.tokens import default_token_generator
from .settings import EMAIL_HOST_USER


class HomePage(TemplateView):
    template_name = 'landingpage/index.html'

class AboutPage(TemplateView):
    template_name = "about.html"

class HelpPage(TemplateView):
    template_name = "help_center.html"

class ContactPage(TemplateView):
    template_name = "contact.html"

class SignupView(FormView):
    template_name = 'signup.html'
    form_class = CustomUserCreationForm
    success_url = reverse_lazy('kyc_submission')

    def form_valid(self, form):
        user = form.save()
        # Send email verification in background
        self.send_verification_email(user)
        login(self.request, user)
        return super().form_valid(form)

    def form_invalid(self, form):
        # Optionally, you can add a message here for form submission failure
        messages.error(self.request, "Please correct the errors below.")
        return super().form_invalid(form)

    def send_verification_email(self, user):
        current_site = get_current_site(self.request)
        mail_subject = 'Verify your email address'

        # UID encoding and token generation
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)  # Use the default token generator

        # Log the UID and token for debugging
        print(f"UID: {uid}")
        print(f"Token: {token}")

        verification_link = f"{self.request.scheme}://{current_site.domain}{reverse('email_verify', kwargs={'uidb64': uid, 'token': token})}"
        message = render_to_string('email_verification_email.html', {
            'user': user,
            'verification_link': verification_link,
        })

        mail = EmailMessage(subject=mail_subject, body=message, from_email=EMAIL_HOST_USER, to=[user.email])
        mail.content_subtype = 'html'
        mail.send()
        user.token = token
        user.save()


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
            # Check if the user has KYC
            try:
                user_kyc = user.kyc  # Check if the user has a KYC submission
            except AttributeError:
                # If the user has no KYC submission, redirect to the KYC submission page
                return redirect('kyc_submission')

            if user_kyc.status == 'approved':
                login(self.request, user)
                return super().form_valid(form)
            else:
                # If KYC is not approved, redirect to the KYC pending page
                return redirect('kyc_pending')
        else:
            messages.error(self.request, "Invalid email or password.")

            return self.form_invalid(form)


def verify_email(request, uidb64, token):
    try:
        # Decode the UID from the URL
        uid = urlsafe_base64_decode(uidb64).decode()
        user = CustomUser.objects.get(pk=uid)

        # Debugging logs for UID and token
        print(f"Decoded UID: {uid}")
        print(f"Received Token: {token}")

    except (TypeError, ValueError, OverflowError, CustomUser.DoesNotExist):
        user = None

    # Check if the user exists and the token is valid
    if user is not None and user.token == token:
        user.is_verified = True
        user.save()
        messages.success(request, 'Your email has been verified.')
        return redirect('dashboard')
    else:
        # Invalid or expired token
        messages.error(request, 'Verification link is invalid or expired!')
        return redirect('signup')


def resend_verify_email(request):
    user = request.user
    current_site = get_current_site(request)
    mail_subject = 'Verify your email address'

    # UID encoding and token generation
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)  # Use the default token generator

    # Log the UID and token for debugging
    print(f"UID: {uid}")
    print(f"Token: {token}")

    verification_link = f"{request.scheme}://{current_site.domain}{reverse('email_verify', kwargs={'uidb64': uid, 'token': token})}"
    message = render_to_string('email_verification_email.html', {
        'user': user,
        'verification_link': verification_link,
    })

    mail = EmailMessage(subject=mail_subject, body=message, from_email=EMAIL_HOST_USER, to=[user.email])
    mail.content_subtype = 'html'
    mail.send()
    user.token = token
    user.save()
    return redirect('dashboard')


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
        start_date_str = self.request.GET.get('start_date')
        end_date_str = self.request.GET.get('end_date')
        print("Trade user group ", self.request.user.trade_group.all()[0])

        trades_queryset = Trade.objects.filter(trade_group__in=self.request.user.trade_group.all())
        trades = trades_queryset.none()

        # Default: Show all trades if no filter is selected
        if date_filter == 'today':
            # Filter trades that occurred today
            start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
            # trades = Trade.objects.filter(user=self.request.user, trade_time__gte=start_of_day)
            trades = trades_queryset.filter(trade_time__gte=start_of_day)

        elif date_filter == 'yesterday':
            # Filter trades that occurred yesterday
            start_of_yesterday = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            end_of_yesterday = (now - timedelta(days=1)).replace(hour=23, minute=59, second=59, microsecond=999999)
            # trades = Trade.objects.filter(user=self.request.user, trade_time__range=[start_of_yesterday, end_of_yesterday])
            trades = trades_queryset.filter(trade_time__range=[start_of_yesterday, end_of_yesterday])

        elif date_filter == '7_days':
            # Filter trades that occurred in the last 7 days
            start_of_7_days_ago = now - timedelta(days=7)
            # trades = Trade.objects.filter(user=self.request.user, trade_time__gte=start_of_7_days_ago)
            trades = trades_queryset.filter(user=self.request.user, trade_time__gte=start_of_7_days_ago)

        elif date_filter == '30_days':
            start_of_30_days_ago = now - timedelta(days=30)
            trades = trades_queryset.filter(user=self.request.user, trade_time__gte=start_of_30_days_ago)

        elif date_filter == '6_months':
            start_of_6_months_ago = now - timedelta(days=182)
            trades = trades_queryset.filter(user=self.request.user, trade_time__gte=start_of_6_months_ago)

        elif date_filter == '1_year':
            start_of_1_year_ago = now - timedelta(days=365)
            trades = trades_queryset.filter(user=self.request.user, trade_time__gte=start_of_1_year_ago)

        elif date_filter == 'custom' and start_date_str and end_date_str:
            try:
                start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
                end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()

                if end_date < start_date:
                    start_date, end_date = end_date, start_date

                start_datetime = timezone.make_aware(datetime.combine(start_date, datetime.min.time()))
                end_datetime = timezone.make_aware(datetime.combine(end_date, datetime.max.time()))
                trades = trades_queryset.filter(user=self.request.user, trade_time__range=[start_datetime, end_datetime])
            except ValueError:
                trades = trades_queryset.none()

        else:
            # Default: Show today's trades if no filter is selected
            start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
            trades = trades_queryset.filter(user=self.request.user, trade_time__gte=start_of_day)

        # Calculate the total profit from the filtered trades
        total_profit = sum(trade.profit for trade in trades)
        context['total_profit'] = total_profit

        context['trades'] = trades
        context['date_filter'] = date_filter  # To pass selected filter value to the template
        context['start_date'] = start_date_str
        context['end_date'] = end_date_str
        return context


class KYCSubmissionView(View):
    template_name = 'kyc_submission.html'

    def get(self, request, *args, **kwargs):
        # Check if the user already has a KYC submission
        if KYC.objects.filter(user=request.user).exists():
            messages.error(request, "You have already submitted a KYC request.")
            return redirect('kyc_pending')  # Redirect to a page showing "KYC under review" or status

        # If no KYC exists, render the KYC form
        form = KYCForm()
        return render(request, self.template_name, {'form': form})

    def post(self, request, *args, **kwargs):
        # Check if the user already has a KYC submission
        if KYC.objects.filter(user=request.user).exists():
            messages.error(request, "You have already submitted a KYC request.")
            return redirect('kyc_pending')  # Redirect to a page showing "KYC under review" or status

        # If no existing KYC, process the new submission
        form = KYCForm(request.POST, request.FILES)

        if form.is_valid():
            # Set the user before saving the form
            kyc_instance = form.save(commit=False)
            kyc_instance.user = request.user  # Assign the logged-in user
            kyc_instance.save()  # Save the form instance

            messages.success(request, "Your KYC submission is under review.")
            return redirect('kyc_pending')  # Redirect to a page showing "KYC under review"
        else:
            # Print errors in the console for debugging
            print(f"Form errors: {form.errors}")
            
            # Do NOT redirect - just return the rendered template with the form that has errors
            return render(request, self.template_name, {'form': form})


class KYCPendingView(LoginRequiredMixin, TemplateView):
    template_name = 'kyc_pending.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        # Check if user has a KYC instance and get status
        if hasattr(user, 'kyc') and user.kyc:
            context['kyc_status'] = user.kyc.status
        else:
            # If no KYC instance exists, redirect to KYC submission page
            return redirect('kyc_submission')

        return context
