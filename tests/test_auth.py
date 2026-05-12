import pytest
from app import main

@pytest.fixture(autouse=True)
def mock_emails(monkeypatch):
    monkeypatch.setattr(main, "send_otp_email", lambda email, otp: True)
    monkeypatch.setattr(main, "send_account_created_email", lambda email, name: True)
    monkeypatch.setattr(main, "send_password_changed_email", lambda email, name: True)
    monkeypatch.setattr(main, "send_notification_email", lambda *args, **kwargs: True)

def test_root(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["message"] == "KampuLynk User Management API is running"

def test_signup(client):
    payload = {
        "fullName": "Auth Test User",
        "email": "authtest@university.edu",
        "password": "StrongPass123",
        "university": "MIT",
        "major": "CS",
        "educationLevel": "bachelors",
        "consentGiven": True
    }
    response = client.post("/auth/signup", json=payload)
    assert response.status_code == 201
    assert "accessToken" in response.json()["data"]

def test_verify_otp(client, monkeypatch):
    captured_otp = []
    monkeypatch.setattr(main, "send_otp_email", lambda email, otp: captured_otp.append(otp))
    
    email = "verifyotp@university.edu"
    client.post("/auth/signup", json={
        "fullName": "Verify User",
        "email": email,
        "password": "StrongPass123",
        "consentGiven": True,
        "university": "MIT",
        "major": "CS",
        "educationLevel": "bachelors"
    })
    
    otp = captured_otp[0]
    response = client.post("/auth/verify-otp", json={"email": email, "otp": otp})
    assert response.status_code == 200
    assert response.json()["message"] == "Email verified"

def test_resend_otp(client, monkeypatch):
    captured_otp = []
    monkeypatch.setattr(main, "send_otp_email", lambda email, otp: captured_otp.append(otp))
    
    email = "resendotp@university.edu"
    client.post("/auth/signup", json={
        "fullName": "Resend User",
        "email": email,
        "password": "StrongPass123",
        "consentGiven": True,
        "university": "MIT",
        "major": "CS",
        "educationLevel": "bachelors"
    })
    
    # Resend
    response = client.post("/auth/resend-otp", json={"email": email})
    assert response.status_code == 200
    assert len(captured_otp) == 2 

def test_login(client):
    email = "login@university.edu"
    password = "StrongPass123"
    client.post("/auth/signup", json={
        "fullName": "Login User",
        "email": email,
        "password": password,
        "consentGiven": True,
        "university": "MIT",
        "major": "CS",
        "educationLevel": "bachelors"
    })
    
    response = client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    assert "accessToken" in response.json()["data"]

def test_social_login(client):
    payload = {
        "provider": "google",
        "idToken": "fake-token",
        "email": "social@university.edu",
        "fullName": "Social User"
    }
    response = client.post("/auth/social", json=payload)
    assert response.status_code == 200
    assert response.json()["data"]["user"]["loginType"] == "google"

def test_refresh_token(client):
    email = "refresh@university.edu"
    signup = client.post("/auth/signup", json={
        "fullName": "Refresh User",
        "email": email,
        "password": "StrongPass123",
        "consentGiven": True,
        "university": "MIT",
        "major": "CS",
        "educationLevel": "bachelors"
    })
    refresh_token = signup.json()["data"]["refreshToken"]
    
    response = client.post("/auth/refresh", json={"refreshToken": refresh_token})
    assert response.status_code == 200
    assert "accessToken" in response.json()["data"]

def test_logout(client, auth_headers):
    email = "logout@university.edu"
    signup = client.post("/auth/signup", json={
        "fullName": "Logout User",
        "email": email,
        "password": "StrongPass123",
        "consentGiven": True,
        "university": "MIT",
        "major": "CS",
        "educationLevel": "bachelors"
    })
    token = signup.json()["data"]["accessToken"]
    
    response = client.post("/auth/logout", headers=auth_headers(token))
    assert response.status_code == 200
    
    me = client.get("/users/me", headers=auth_headers(token))
    assert me.status_code == 401

def test_admin_signup(client):
    payload = {
        "fullName": "Admin New",
        "email": "admin.new@university.edu",
        "password": "StrongPass123",
        "consentGiven": True,
        "university": "MIT",
        "major": "CS",
        "educationLevel": "bachelors"
    }
    response = client.post("/auth/admin/signup", json=payload)
    assert response.status_code == 201
    assert response.json()["data"]["user"]["role"] == "superadmin"

def test_admin_signin(client):
    email = "admin.signin@university.edu"
    password = "StrongPass123"
    client.post("/auth/admin/signup", json={
        "fullName": "Admin Signin",
        "email": email,
        "password": password,
        "consentGiven": True,
        "university": "MIT",
        "major": "CS",
        "educationLevel": "bachelors"
    })
    
    response = client.post("/auth/admin/signin", json={"email": email, "password": password})
    assert response.status_code == 200
    assert response.json()["data"]["user"]["role"] == "superadmin"
