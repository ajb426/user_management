import pytest
from httpx import AsyncClient
from app.main import app
from app.models.user_model import User,  UserRole
from app.services.jwt_service import create_access_token
from datetime import timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.email_service import EmailService
from unittest.mock import AsyncMock
import uuid


@pytest.mark.asyncio
async def test_update_profile_success(db_session, current_user, async_client):
    # Ensure the current_user has valid URL fields
    current_user.profile_picture_url = "https://example.com/profile.jpg"
    current_user.linkedin_profile_url = "https://linkedin.com/in/example"
    current_user.github_profile_url = "https://github.com/example"

    # Create a valid token for the current_user
    access_token = create_access_token(data={"sub": str(current_user.id), "role": current_user.role.name})
    headers = {"Authorization": f"Bearer {access_token}"}

    # Prepare the update data
    update_data = {
        "first_name": "UpdatedFirstName",
        "last_name": "UpdatedLastName",
        "bio": "Updated bio",
        "location": "New York, NY"
    }

    response = await async_client.put("/profile", json=update_data, headers=headers)

    response_data = response.json()
    print("Response JSON:", response_data)  # Debugging: Print the response JSON
    print("Current User Data:", vars(current_user))  # Debugging: Print the current user data

    assert response.status_code == 200, response.json()
    assert response_data["first_name"] == "UpdatedFirstName"
    assert response_data["last_name"] == "UpdatedLastName"
    assert response_data["bio"] == "Updated bio"
    assert response_data["location"] == "New York, NY"


@pytest.mark.asyncio
async def test_upgrade_user_to_professional_success(async_client: AsyncClient, manager_user: User, db_session: AsyncSession, email_service: EmailService):
    # Create a regular user to be upgraded
    user_data = {
        "nickname": "regular_user",
        "email": "regular@example.com",
        "first_name": "Regular",
        "last_name": "User",
        "hashed_password": "Secure*1234",
        "role": UserRole.ANONYMOUS,
        "email_verified": True
    }
    user = User(**user_data)
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    # Mock email service to avoid sending actual emails during tests
    email_service.send_professional_status_upgrade_email = AsyncMock()

    # Create a valid token for the manager user
    access_token = create_access_token(data={"sub": str(manager_user.id), "role": manager_user.role.name})
    headers = {"Authorization": f"Bearer {access_token}"}

    response = await async_client.put(f"/users/{user.id}/upgrade", headers=headers)
    response_data = response.json()

    print("Response JSON:", response_data)  # Debugging: Print the response JSON

    assert response.status_code == 200, response.json()
    assert response_data["is_professional"] is True

    # Verify the database record is updated
    updated_user = await db_session.get(User, user.id)
    assert updated_user.is_professional is True, "User is_professional should be True in the database"

@pytest.mark.asyncio
async def test_upgrade_user_not_found(db_session: AsyncSession, manager_user: User, email_service: EmailService, async_client: AsyncClient):
    # Create a valid token for the manager user
    access_token = create_access_token(data={"sub": str(manager_user.id), "role": manager_user.role.name})
    headers = {"Authorization": f"Bearer {access_token}"}

    zero_uuid = str(uuid.UUID(int=0))

    response = await async_client.put(f"/users/{zero_uuid}/upgrade", headers=headers)
    response_data = response.json()

    assert response.status_code == 404
    assert response_data["detail"] == "User not found"

@pytest.mark.asyncio
async def test_upgrade_user_unauthorized(db_session: AsyncSession, current_user: User, async_client: AsyncClient):
    # Create a regular user to be upgraded
    user_data = {
        "nickname": "regular_user",
        "email": "regular@example.com",
        "first_name": "Regular",
        "last_name": "User",
        "hashed_password": "Secure*1234",
        "role": UserRole.ANONYMOUS,
        "email_verified": True
    }
    user = User(**user_data)
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    # Create a valid token for the current user (not a manager or admin)
    access_token = create_access_token(data={"sub": str(current_user.id), "role": current_user.role.name})
    headers = {"Authorization": f"Bearer {access_token}"}

    response = await async_client.put(f"/users/{user.id}/upgrade", headers=headers)
    response_data = response.json()

    assert response.status_code == 403
    assert response_data["detail"] == "Not authorized"

@pytest.mark.asyncio
async def test_update_profile_validation(async_client: AsyncClient, current_user: User):
    # Create a valid token for the current_user
    access_token = create_access_token(data={"sub": str(current_user.id), "role": current_user.role.name})
    headers = {"Authorization": f"Bearer {access_token}"}

    # Test invalid boolean value for is_professional
    response = await async_client.put("/profile", json={
        "first_name": "UpdatedFirstName",
        "last_name": "UpdatedLastName",
        "bio": "Updated bio",
        "is_professional": "not_a_boolean"
    }, headers=headers)

    assert response.status_code == 422
    response_data = response.json()
    assert "value is not a valid boolean" in str(response_data), "Expected boolean validation error"

    # Test missing professional_status_updated_at when is_professional is True
    response = await async_client.put("/profile", json={
        "first_name": "UpdatedFirstName",
        "last_name": "UpdatedLastName",
        "bio": "Updated bio",
        "is_professional": True
    }, headers=headers)

    assert response.status_code == 422
    response_data = response.json()
    assert "professional_status_updated_at must be set if is_professional is True" in str(response_data), "Expected validation error for missing professional_status_updated_at"
