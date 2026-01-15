# Gym Management API

A comprehensive Django-based REST API for managing gym operations including multi-branch management, subscription-based access, member management, payment tracking, and Hikvision access control integration.

## Features

### Core Functionality

- **Multi-tenant Gym Management**: Subscription-based gym accounts with different tiers
- **Branch Management**: Add and manage multiple gym branches based on subscription plan
- **Staff Management**: Role-based access control for gym staff across branches
- **Member Management**: Complete member lifecycle from registration to subscription renewal
- **Subscription Plans**: Flexible membership plans with customizable durations and features
- **Payment Processing**: Income and expense tracking with detailed financial records
- **Hikvision Integration**: Automated access control for gym entry/exit using Hikvision devices
- **Food Logging**: Track member nutrition and meal plans
- **Attendance Tracking**: Monitor member check-ins and gym usage patterns

### Subscription Tiers

Different gym subscription levels provide access to:
- Number of branches allowed
- Number of staff accounts
- Advanced features (analytics, reports, integrations)
- API rate limits
- Storage limits

## Technology Stack

- **Backend**: Django 4.x + Django REST Framework
- **Database**: PostgreSQL
- **Authentication**: JWT (djangorestframework-simplejwt)
- **Access Control**: Hikvision SDK integration
- **Task Queue**: Celery + Redis
- **Documentation**: drf-spectacular (OpenAPI 3.0)
- **Testing**: pytest + pytest-django

## Installation

### Prerequisites

- Python 3.10+
- PostgreSQL 13+
- Redis 6+
- Hikvision Access Control Device (for access control features)

### Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd gym-management-api
```

2. Create virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Configure environment variables:
```bash
cp .env.example .env
# Edit .env with your configuration
```

5. Run migrations:
```bash
python manage.py migrate
```

6. Create superuser:
```bash
python manage.py createsuperuser
```

7. Run development server:
```bash
python manage.py runserver
```

## Environment Variables

```env
# Django Settings
SECRET_KEY=your-secret-key
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database
DB_NAME=gym_db
DB_USER=gym_user
DB_PASSWORD=your-password
DB_HOST=localhost
DB_PORT=5432

# Redis
REDIS_URL=redis://localhost:6379/0

# JWT Settings
JWT_ACCESS_TOKEN_LIFETIME=60  # minutes
JWT_REFRESH_TOKEN_LIFETIME=1  # days

# Hikvision Access Control
HIK_DEVICE_IP=192.168.1.100
HIK_DEVICE_PORT=80
HIK_USERNAME=admin
HIK_PASSWORD=admin123

# Payment Gateway (if applicable)
PAYMENT_GATEWAY_KEY=your-key
PAYMENT_GATEWAY_SECRET=your-secret
```

## API Documentation

### Authentication

All API endpoints (except registration and login) require JWT authentication.

**Obtain Token:**
```http
POST /api/auth/login/
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "password123"
}
```

**Use Token:**
```http
Authorization: Bearer <access_token>
```

### Key Endpoints

#### Gym Management
- `POST /api/gyms/` - Create new gym account
- `GET /api/gyms/{id}/` - Get gym details
- `PATCH /api/gyms/{id}/` - Update gym information
- `GET /api/gyms/{id}/subscription/` - View subscription status

#### Branch Management
- `POST /api/branches/` - Create new branch
- `GET /api/branches/` - List all branches
- `GET /api/branches/{id}/` - Get branch details
- `PATCH /api/branches/{id}/` - Update branch
- `DELETE /api/branches/{id}/` - Delete branch

#### Staff Management
- `POST /api/staff/` - Add staff member
- `GET /api/staff/` - List staff
- `PATCH /api/staff/{id}/` - Update staff details
- `POST /api/staff/{id}/assign-branch/` - Assign to branch

#### Member Management
- `POST /api/members/` - Register new member
- `GET /api/members/` - List members
- `GET /api/members/{id}/` - Get member details
- `PATCH /api/members/{id}/` - Update member
- `GET /api/members/{id}/subscription/` - View member subscription

#### Subscriptions
- `POST /api/subscriptions/plans/` - Create subscription plan
- `GET /api/subscriptions/plans/` - List available plans
- `POST /api/subscriptions/enroll/` - Enroll member in plan
- `POST /api/subscriptions/renew/` - Renew subscription

#### Payments
- `POST /api/payments/income/` - Record income
- `POST /api/payments/expense/` - Record expense
- `GET /api/payments/transactions/` - List transactions
- `GET /api/payments/reports/` - Financial reports

#### Access Control
- `POST /api/access/register-device/` - Register Hikvision device
- `POST /api/access/grant/` - Grant member access
- `POST /api/access/revoke/` - Revoke member access
- `GET /api/access/logs/` - Access logs

#### Food Logging
- `POST /api/nutrition/meals/` - Log meal
- `GET /api/nutrition/meals/` - List member meals
- `GET /api/nutrition/stats/{member_id}/` - Nutrition statistics
- `POST /api/nutrition/plans/` - Create meal plan

### Interactive API Documentation

Visit `/api/docs/` for Swagger UI documentation
Visit `/api/redoc/` for ReDoc documentation

## Database Schema

### Key Models

**Gym**: Main gym account with subscription tier
**Branch**: Individual gym locations
**Staff**: Gym employees with role-based permissions
**Member**: Gym members/customers
**SubscriptionPlan**: Available membership plans
**MemberSubscription**: Active member subscriptions
**Payment**: Income and expense transactions
**AccessLog**: Entry/exit records from Hikvision
**FoodLog**: Member nutrition tracking
**Attendance**: Member check-in records

## Hikvision Integration

### Setup

1. Ensure Hikvision device is on the same network
2. Configure device IP and credentials in `.env`
3. Register device through API or admin panel
4. Sync members to access control system

### Features

- Automatic member registration on device
- Face/card-based access control
- Real-time entry/exit logging
- Access revocation on subscription expiry
- Multi-device support for multiple branches

### Sync Command

```bash
python manage.py sync_access_control
```

## Payment Integration

The system supports multiple payment gateways. Configure your preferred gateway in settings:

- Stripe
- Razorpay
- PayPal
- Manual/Cash payments

## Celery Tasks

Background tasks handled by Celery:

- Subscription expiry notifications
- Access control synchronization
- Payment reminders
- Report generation
- Data backups

**Start Celery worker:**
```bash
celery -A gym_management worker -l info
```

**Start Celery beat (scheduler):**
```bash
celery -A gym_management beat -l info
```

## Testing

Run tests with pytest:

```bash
# All tests
pytest

# With coverage
pytest --cov=.

# Specific test file
pytest apps/members/tests/test_api.py
```

## Permissions & Roles

### Staff Roles

- **Gym Owner**: Full access to all features
- **Manager**: Branch management, staff, and members
- **Trainer**: Member management and training logs
- **Receptionist**: Member check-in, basic info
- **Accountant**: Financial records and reports

### API Permissions

Permissions are enforced at both the API and database level using Django's permission system and custom permission classes.

## Deployment

### Production Checklist

- [ ] Set `DEBUG=False`
- [ ] Configure proper `ALLOWED_HOSTS`
- [ ] Use strong `SECRET_KEY`
- [ ] Set up PostgreSQL with proper credentials
- [ ] Configure Redis for production
- [ ] Set up SSL/TLS certificates
- [ ] Configure CORS settings
- [ ] Set up monitoring and logging
- [ ] Configure backup strategy
- [ ] Set up Celery workers with supervisord
- [ ] Configure media/static files serving

### Recommended Stack

- **Server**: Ubuntu 22.04 LTS
- **Web Server**: Nginx
- **Application Server**: Gunicorn
- **Process Manager**: Supervisord
- **SSL**: Let's Encrypt

## Monitoring

- Application logs: `/logs/django.log`
- Access logs: `/logs/access.log`
- Error tracking: Configure Sentry
- Performance monitoring: Django Debug Toolbar (dev only)

## API Rate Limiting

Rate limits based on subscription tier:

- Basic: 100 requests/minute
- Pro: 500 requests/minute
- Enterprise: 2000 requests/minute

## Support & Documentation

- Full API documentation: `/api/docs/`
- Admin panel: `/admin/`
- Technical documentation: `/docs/`

## Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit changes (`git commit -m 'Add AmazingFeature'`)
4. Push to branch (`git push origin feature/AmazingFeature`)
5. Open Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Version History

- **v1.0.0** (2024-01-15): Initial release
  - Core gym management features
  - Hikvision integration
  - Payment tracking
  - Food logging

## Contact

For support or inquiries, please contact support@gymmanagement.com
