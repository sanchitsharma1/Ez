from fastapi import APIRouter, HTTPException, Depends, status, Query, File, UploadFile
from typing import List, Dict, Any, Optional
import logging
from datetime import datetime
import uuid

from middleware.auth import get_current_active_user
from models.database import User
from models.schemas import EmailRequest, EmailResponse, EmailThread, EmailAccount, EmailStats

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/accounts", response_model=List[EmailAccount])
async def get_email_accounts(
    current_user: User = Depends(get_current_active_user)
):
    """Get user's configured email accounts"""
    try:
        from core.database import get_db_session
        from models.database import EmailAccountConfig
        from sqlalchemy import select
        
        async with get_db_session() as session:
            query = select(EmailAccountConfig).where(
                EmailAccountConfig.user_id == current_user.id,
                EmailAccountConfig.is_active == True
            )
            result = await session.execute(query)
            accounts = result.scalars().all()
            
            return [
                EmailAccount(
                    id=account.id,
                    email_address=account.email_address,
                    provider=account.provider,
                    display_name=account.display_name,
                    is_default=account.is_default,
                    is_active=account.is_active,
                    last_sync=account.last_sync,
                    created_at=account.created_at
                )
                for account in accounts
            ]
            
    except Exception as e:
        logger.error(f"Error retrieving email accounts: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve email accounts: {str(e)}"
        )

@router.post("/accounts", response_model=EmailAccount)
async def add_email_account(
    email_address: str,
    provider: str,
    display_name: Optional[str] = None,
    current_user: User = Depends(get_current_active_user)
):
    """Add a new email account"""
    try:
        from core.database import get_db_session
        from models.database import EmailAccountConfig
        
        # Validate provider
        if provider not in ["gmail", "zoho"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unsupported email provider. Supported: gmail, zoho"
            )
        
        async with get_db_session() as session:
            # Check if account already exists
            from sqlalchemy import select
            existing_query = select(EmailAccountConfig).where(
                EmailAccountConfig.user_id == current_user.id,
                EmailAccountConfig.email_address == email_address
            )
            existing_result = await session.execute(existing_query)
            if existing_result.scalar_one_or_none():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email account already configured"
                )
            
            # Create new account config
            new_account = EmailAccountConfig(
                id=uuid.uuid4(),
                user_id=current_user.id,
                email_address=email_address,
                provider=provider,
                display_name=display_name or email_address,
                is_default=False,  # Set first account as default
                is_active=True,
                created_at=datetime.utcnow()
            )
            
            # Check if this is the first account
            count_query = select(EmailAccountConfig).where(
                EmailAccountConfig.user_id == current_user.id
            )
            count_result = await session.execute(count_query)
            if not count_result.scalars().first():
                new_account.is_default = True
            
            session.add(new_account)
            await session.commit()
            await session.refresh(new_account)
            
            # Initiate OAuth flow for the provider
            oauth_url = await initiate_email_oauth(new_account, provider)
            
            return EmailAccount(
                id=new_account.id,
                email_address=new_account.email_address,
                provider=new_account.provider,
                display_name=new_account.display_name,
                is_default=new_account.is_default,
                is_active=new_account.is_active,
                last_sync=new_account.last_sync,
                created_at=new_account.created_at,
                oauth_url=oauth_url
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding email account: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add email account: {str(e)}"
        )

@router.get("/messages", response_model=List[EmailResponse])
async def get_emails(
    account_id: Optional[uuid.UUID] = Query(None),
    folder: str = Query("inbox"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    unread_only: bool = Query(False),
    current_user: User = Depends(get_current_active_user)
):
    """Get email messages"""
    try:
        from core.database import get_db_session
        from models.database import EmailMessage
        from sqlalchemy import select
        
        async with get_db_session() as session:
            # Build query
            query = select(EmailMessage).where(EmailMessage.user_id == current_user.id)
            
            if account_id:
                query = query.where(EmailMessage.account_id == account_id)
            if folder:
                query = query.where(EmailMessage.folder == folder)
            if unread_only:
                query = query.where(EmailMessage.is_read == False)
            
            query = query.order_by(EmailMessage.received_at.desc()).limit(limit).offset(offset)
            
            result = await session.execute(query)
            messages = result.scalars().all()
            
            return [
                EmailResponse(
                    id=msg.id,
                    account_id=msg.account_id,
                    message_id=msg.message_id,
                    thread_id=msg.thread_id,
                    subject=msg.subject,
                    sender=msg.sender,
                    recipients=msg.recipients or [],
                    cc=msg.cc or [],
                    bcc=msg.bcc or [],
                    body_text=msg.body_text,
                    body_html=msg.body_html,
                    attachments=msg.attachments or [],
                    is_read=msg.is_read,
                    is_starred=msg.is_starred,
                    folder=msg.folder,
                    labels=msg.labels or [],
                    received_at=msg.received_at,
                    created_at=msg.created_at
                )
                for msg in messages
            ]
            
    except Exception as e:
        logger.error(f"Error retrieving emails: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve emails: {str(e)}"
        )

@router.post("/send", response_model=EmailResponse)
async def send_email(
    email_data: EmailRequest,
    attachments: Optional[List[UploadFile]] = File(None),
    current_user: User = Depends(get_current_active_user)
):
    """Send an email"""
    try:
        from core.database import get_db_session
        from models.database import EmailMessage, EmailAccountConfig
        from sqlalchemy import select
        
        # Get sender account
        async with get_db_session() as session:
            if email_data.account_id:
                account_query = select(EmailAccountConfig).where(
                    EmailAccountConfig.id == email_data.account_id,
                    EmailAccountConfig.user_id == current_user.id
                )
            else:
                # Use default account
                account_query = select(EmailAccountConfig).where(
                    EmailAccountConfig.user_id == current_user.id,
                    EmailAccountConfig.is_default == True
                )
            
            account_result = await session.execute(account_query)
            account = account_result.scalar_one_or_none()
            
            if not account:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No email account found"
                )
            
            # Process attachments if any
            attachment_data = []
            if attachments:
                for attachment in attachments:
                    content = await attachment.read()
                    attachment_data.append({
                        "filename": attachment.filename,
                        "content_type": attachment.content_type,
                        "size": len(content),
                        "data": content
                    })
            
            # Send email through provider
            sent_message = await send_email_via_provider(
                account=account,
                subject=email_data.subject,
                body_text=email_data.body_text,
                body_html=email_data.body_html,
                recipients=email_data.recipients,
                cc=email_data.cc or [],
                bcc=email_data.bcc or [],
                attachments=attachment_data,
                in_reply_to=email_data.in_reply_to
            )
            
            # Store sent message in database
            new_message = EmailMessage(
                id=uuid.uuid4(),
                account_id=account.id,
                user_id=current_user.id,
                message_id=sent_message.get("message_id", str(uuid.uuid4())),
                subject=email_data.subject,
                sender=account.email_address,
                recipients=email_data.recipients,
                cc=email_data.cc or [],
                bcc=email_data.bcc or [],
                body_text=email_data.body_text,
                body_html=email_data.body_html,
                attachments=[{
                    "filename": att["filename"],
                    "content_type": att["content_type"],
                    "size": att["size"]
                } for att in attachment_data],
                folder="sent",
                is_read=True,
                received_at=datetime.utcnow(),
                created_at=datetime.utcnow(),
                sent_by_agent=email_data.sent_by_agent
            )
            
            session.add(new_message)
            await session.commit()
            await session.refresh(new_message)
            
            return EmailResponse(
                id=new_message.id,
                account_id=new_message.account_id,
                message_id=new_message.message_id,
                subject=new_message.subject,
                sender=new_message.sender,
                recipients=new_message.recipients,
                cc=new_message.cc or [],
                bcc=new_message.bcc or [],
                body_text=new_message.body_text,
                body_html=new_message.body_html,
                attachments=new_message.attachments or [],
                is_read=new_message.is_read,
                folder=new_message.folder,
                received_at=new_message.received_at,
                created_at=new_message.created_at
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending email: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send email: {str(e)}"
        )

@router.post("/reply/{message_id}", response_model=EmailResponse)
async def reply_to_email(
    message_id: uuid.UUID,
    reply_data: EmailRequest,
    attachments: Optional[List[UploadFile]] = File(None),
    current_user: User = Depends(get_current_active_user)
):
    """Reply to an email"""
    try:
        from core.database import get_db_session
        from models.database import EmailMessage
        from sqlalchemy import select
        
        async with get_db_session() as session:
            # Get original message
            query = select(EmailMessage).where(
                EmailMessage.id == message_id,
                EmailMessage.user_id == current_user.id
            )
            result = await session.execute(query)
            original_message = result.scalar_one_or_none()
            
            if not original_message:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Original message not found"
                )
            
            # Prepare reply
            reply_request = EmailRequest(
                account_id=original_message.account_id,
                subject=f"Re: {original_message.subject}" if not original_message.subject.startswith("Re:") else original_message.subject,
                body_text=reply_data.body_text,
                body_html=reply_data.body_html,
                recipients=[original_message.sender],
                cc=reply_data.cc or [],
                bcc=reply_data.bcc or [],
                in_reply_to=original_message.message_id,
                sent_by_agent=reply_data.sent_by_agent
            )
            
            return await send_email(reply_request, attachments, current_user)
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error replying to email {message_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reply to email: {str(e)}"
        )

@router.get("/messages/{message_id}", response_model=EmailResponse)
async def get_email_message(
    message_id: uuid.UUID,
    mark_as_read: bool = Query(True),
    current_user: User = Depends(get_current_active_user)
):
    """Get a specific email message"""
    try:
        from core.database import get_db_session
        from models.database import EmailMessage
        from sqlalchemy import select
        
        async with get_db_session() as session:
            query = select(EmailMessage).where(
                EmailMessage.id == message_id,
                EmailMessage.user_id == current_user.id
            )
            result = await session.execute(query)
            message = result.scalar_one_or_none()
            
            if not message:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Email message not found"
                )
            
            # Mark as read if requested
            if mark_as_read and not message.is_read:
                message.is_read = True
                await session.commit()
            
            return EmailResponse(
                id=message.id,
                account_id=message.account_id,
                message_id=message.message_id,
                thread_id=message.thread_id,
                subject=message.subject,
                sender=message.sender,
                recipients=message.recipients or [],
                cc=message.cc or [],
                bcc=message.bcc or [],
                body_text=message.body_text,
                body_html=message.body_html,
                attachments=message.attachments or [],
                is_read=message.is_read,
                is_starred=message.is_starred,
                folder=message.folder,
                labels=message.labels or [],
                received_at=message.received_at,
                created_at=message.created_at
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving email message {message_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve email message: {str(e)}"
        )

@router.post("/sync")
async def sync_email_accounts(
    account_id: Optional[uuid.UUID] = Query(None),
    current_user: User = Depends(get_current_active_user)
):
    """Sync email accounts with providers"""
    try:
        from core.database import get_db_session
        from models.database import EmailAccountConfig
        from sqlalchemy import select
        
        async with get_db_session() as session:
            # Get accounts to sync
            if account_id:
                query = select(EmailAccountConfig).where(
                    EmailAccountConfig.id == account_id,
                    EmailAccountConfig.user_id == current_user.id
                )
            else:
                query = select(EmailAccountConfig).where(
                    EmailAccountConfig.user_id == current_user.id,
                    EmailAccountConfig.is_active == True
                )
            
            result = await session.execute(query)
            accounts = result.scalars().all()
            
            sync_results = []
            for account in accounts:
                try:
                    synced_count = await sync_account_messages(account)
                    sync_results.append({
                        "account_id": str(account.id),
                        "email_address": account.email_address,
                        "synced_messages": synced_count,
                        "status": "success"
                    })
                    
                    # Update last sync time
                    account.last_sync = datetime.utcnow()
                    
                except Exception as e:
                    sync_results.append({
                        "account_id": str(account.id),
                        "email_address": account.email_address,
                        "synced_messages": 0,
                        "status": "error",
                        "error": str(e)
                    })
            
            await session.commit()
            
            return {
                "message": "Email sync completed",
                "sync_results": sync_results,
                "synced_at": datetime.utcnow().isoformat()
            }
            
    except Exception as e:
        logger.error(f"Error syncing email accounts: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to sync email accounts: {str(e)}"
        )

@router.get("/stats", response_model=EmailStats)
async def get_email_stats(
    current_user: User = Depends(get_current_active_user)
):
    """Get email statistics"""
    try:
        from core.database import get_db_session
        from models.database import EmailMessage
        from sqlalchemy import select, func
        
        async with get_db_session() as session:
            # Total messages
            total_query = select(func.count(EmailMessage.id)).where(
                EmailMessage.user_id == current_user.id
            )
            total_result = await session.execute(total_query)
            total_messages = total_result.scalar()
            
            # Unread messages
            unread_query = select(func.count(EmailMessage.id)).where(
                EmailMessage.user_id == current_user.id,
                EmailMessage.is_read == False
            )
            unread_result = await session.execute(unread_query)
            unread_messages = unread_result.scalar()
            
            # Messages by folder
            folder_query = select(EmailMessage.folder, func.count(EmailMessage.id)).where(
                EmailMessage.user_id == current_user.id
            ).group_by(EmailMessage.folder)
            folder_result = await session.execute(folder_query)
            messages_by_folder = {folder: count for folder, count in folder_result}
            
            # Recent activity (last 7 days)
            from datetime import timedelta
            recent_date = datetime.utcnow() - timedelta(days=7)
            recent_query = select(func.count(EmailMessage.id)).where(
                EmailMessage.user_id == current_user.id,
                EmailMessage.received_at >= recent_date
            )
            recent_result = await session.execute(recent_query)
            recent_messages = recent_result.scalar()
            
            return EmailStats(
                total_messages=total_messages,
                unread_messages=unread_messages,
                messages_by_folder=messages_by_folder,
                recent_messages=recent_messages,
                last_sync=datetime.utcnow()  # This would be actual last sync time
            )
            
    except Exception as e:
        logger.error(f"Error getting email stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get email stats: {str(e)}"
        )

# Helper functions

async def initiate_email_oauth(account, provider: str) -> str:
    """Initiate OAuth flow for email provider"""
    # Placeholder for OAuth implementation
    try:
        if provider == "gmail":
            # Return Gmail OAuth URL
            return f"https://accounts.google.com/oauth/authorize?client_id=YOUR_CLIENT_ID&redirect_uri=YOUR_REDIRECT&scope=gmail.readonly+gmail.send&response_type=code"
        elif provider == "zoho":
            # Return Zoho OAuth URL
            return f"https://accounts.zoho.com/oauth/v2/auth?client_id=YOUR_CLIENT_ID&redirect_uri=YOUR_REDIRECT&scope=ZohoMail.messages.ALL&response_type=code"
        else:
            raise ValueError(f"Unsupported provider: {provider}")
    except Exception as e:
        logger.error(f"OAuth initiation failed: {e}")
        raise

async def send_email_via_provider(account, **email_data) -> Dict[str, Any]:
    """Send email through the specified provider"""
    # Placeholder for provider-specific email sending
    try:
        if account.provider == "gmail":
            # Use Gmail API to send email
            return {"message_id": f"gmail_{uuid.uuid4()}", "status": "sent"}
        elif account.provider == "zoho":
            # Use Zoho API to send email
            return {"message_id": f"zoho_{uuid.uuid4()}", "status": "sent"}
        else:
            raise ValueError(f"Unsupported provider: {account.provider}")
    except Exception as e:
        logger.error(f"Email sending failed: {e}")
        raise

async def sync_account_messages(account) -> int:
    """Sync messages for a specific account"""
    # Placeholder for message syncing
    try:
        if account.provider == "gmail":
            # Sync Gmail messages
            return 0  # Return number of synced messages
        elif account.provider == "zoho":
            # Sync Zoho messages
            return 0  # Return number of synced messages
        else:
            return 0
    except Exception as e:
        logger.error(f"Message sync failed for {account.email_address}: {e}")
        raise