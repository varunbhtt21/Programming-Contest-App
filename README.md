# Programming Contest Application

A Streamlit-based web application for conducting programming contests with MCQs and coding questions.

## Features

- Admin Dashboard
  - Add MCQ and coding questions
  - View student results and analytics
  - Secure admin login

- Student Interface
  - Simple registration process
  - 5 MCQ questions (1 mark each)
  - 1 Coding question (5 marks)
  - 40-minute timer
  - Real-time progress tracking

## Prerequisites

- Python 3.x
- MongoDB
- Virtual Environment (recommended)

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd programming-contest-app
```

2. Create and activate virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create a `.env` file in the root directory with the following content:
```
MONGODB_URI=mongodb://localhost:27017/
DB_NAME=programming_contest
ADMIN_USERNAME=admin
ADMIN_PASSWORD=your_secure_password
SECRET_KEY=your_secret_key
```

## Running the Application

1. Make sure MongoDB is running on your system

2. Start the Streamlit application:
```bash
cd src
streamlit run app.py
```

3. Access the application in your browser at `http://localhost:8501`

## Usage

### Admin
1. Select "Admin" role from the sidebar
2. Login with admin credentials
3. Use the dashboard to:
   - Add new questions
   - View student results
   - Monitor test progress

### Students
1. Select "Student" role from the sidebar
2. Register with name and email
3. Complete the test within 40 minutes
4. View results after submission

## Project Structure

```
programming-contest-app/
├── src/
│   ├── admin/
│   │   └── admin_dashboard.py
│   ├── student/
│   │   └── student_dashboard.py
│   ├── database/
│   │   └── mongodb.py
│   └── app.py
├── venv/
├── .env
├── requirements.txt
└── README.md
```

## Security Notes

- Change default admin credentials in production
- Use secure MongoDB configuration
- Keep `.env` file secure and never commit it to version control

## Configuration

### Secrets Configuration
1. Copy `src/.streamlit/secrets.toml.example` to `src/.streamlit/secrets.toml`
2. Update the values in `secrets.toml` with your actual credentials
3. Never commit `secrets.toml` to version control - it's already in `.gitignore`

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request 