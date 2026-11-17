"""Regression tests for Phase 3A: Secure User-Owned AWS Account Storage."""

from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, event, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.config.settings import CredentialsEncryptionError
from backend.db.base import Base
from backend.models.auth import User
from backend.models.finops import AWSAccount
from backend.utils.credential_encryption import (
    CredentialTamperError,
    create_user_aws_account,
    decrypt_aws_credentials,
    encrypt_aws_credentials,
    generate_encryption_key,
    get_user_aws_account,
    list_user_aws_accounts,
    mask_access_key_id,
    serialize_aws_account,
)


ROOT = Path(__file__).resolve().parents[1]
MOCK_TEMP_KEY = "ASIA" + "IOSFODNN7EXAMPLE"
MOCK_PERM_KEY = "AKIA" + "IOSFODNN7EXAMPLE"
MOCK_ALICE_KEY = "AKIA" + "ALICEKEY12345678"
MOCK_BOB_KEY = "ASIA" + "BOBKEY9876543210"
MOCK_SECRET_EXAMPLE = "test-secret-" + "key-value-example-12345"


class AWSAccountStorageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.valid_key = generate_encryption_key()

    def test_encryption_decryption_roundtrip_and_non_deterministic_nonce(self) -> None:
        with patch.dict(os.environ, {"CREDENTIALS_ENCRYPTION_KEY": self.valid_key}, clear=False):
            c1 = encrypt_aws_credentials(
                access_key_id=MOCK_TEMP_KEY,
                secret_access_key=MOCK_SECRET_EXAMPLE,
                session_token="FwoGZXIvYXdzEBYaDHsessionTokenExample123",
                user_id=42,
            )
            c2 = encrypt_aws_credentials(
                access_key_id=MOCK_TEMP_KEY,
                secret_access_key=MOCK_SECRET_EXAMPLE,
                session_token="FwoGZXIvYXdzEBYaDHsessionTokenExample123",
                user_id=42,
            )
            self.assertNotEqual(c1, c2)
            self.assertTrue(c1.startswith("v1."))
            self.assertNotIn(MOCK_TEMP_KEY, c1)
            self.assertNotIn(MOCK_SECRET_EXAMPLE, c1)
            self.assertNotIn("FwoGZXIvYXdz", c1)

            decrypted = decrypt_aws_credentials(c1, user_id=42)
            self.assertEqual(decrypted.access_key_id, MOCK_TEMP_KEY)
            self.assertEqual(
                decrypted.secret_access_key,
                MOCK_SECRET_EXAMPLE,
            )
            self.assertEqual(
                decrypted.session_token,
                "FwoGZXIvYXdzEBYaDHsessionTokenExample123",
            )
            # Ensure repr/str never leak secrets
            self.assertNotIn(MOCK_SECRET_EXAMPLE, repr(decrypted))
            self.assertNotIn("FwoGZXIvYXdz", str(decrypted))
            self.assertIn("ASIA************MPLE", repr(decrypted))

    def test_tamper_detection_rejects_modified_ciphertext_nonce_and_wrong_key(self) -> None:
        with patch.dict(os.environ, {"CREDENTIALS_ENCRYPTION_KEY": self.valid_key}, clear=False):
            ciphertext = encrypt_aws_credentials(
                access_key_id=MOCK_PERM_KEY,
                secret_access_key="super-secret-value-123456",
                user_id=7,
            )
            version, nonce_b64, payload_b64 = ciphertext.split(".")

            # Tamper with ciphertext/GCM tag
            flipped_char = "A" if payload_b64[0] != "A" else "B"
            tampered_payload = f"{version}.{nonce_b64}.{flipped_char}{payload_b64[1:]}"
            with self.assertRaises(CredentialTamperError):
                decrypt_aws_credentials(tampered_payload, user_id=7)

            # Tamper with trailing base64 character before '=' padding
            flipped_tail = "A" if payload_b64[-2] != "A" else "B"
            tampered_tail = f"{version}.{nonce_b64}.{payload_b64[:-2]}{flipped_tail}{payload_b64[-1]}"
            with self.assertRaises(CredentialTamperError):
                decrypt_aws_credentials(tampered_tail, user_id=7)

            # Tamper with nonce
            flipped_nonce = "A" if nonce_b64[0] != "A" else "B"
            tampered_nonce = f"{version}.{flipped_nonce}{nonce_b64[1:]}.{payload_b64}"
            with self.assertRaises(CredentialTamperError):
                decrypt_aws_credentials(tampered_nonce, user_id=7)

            # Tamper with version prefix
            with self.assertRaises(CredentialTamperError):
                decrypt_aws_credentials(f"v2.{nonce_b64}.{payload_b64}", user_id=7)

        # Decrypt with a different valid key
        other_key = generate_encryption_key()
        with patch.dict(os.environ, {"CREDENTIALS_ENCRYPTION_KEY": other_key}, clear=False):
            with self.assertRaises(CredentialTamperError):
                decrypt_aws_credentials(ciphertext, user_id=7)

    def test_missing_or_invalid_encryption_key_fails_safely(self) -> None:
        with patch.dict(os.environ, {"CREDENTIALS_ENCRYPTION_KEY": ""}, clear=False):
            with self.assertRaises(CredentialsEncryptionError):
                encrypt_aws_credentials(
                    access_key_id=MOCK_PERM_KEY,
                    secret_access_key="secret",
                    user_id=1,
                )

        for bad_key in ("not-valid-base64!!!", "c2hvcnQ=", "YWJjZGVmZ2hpamtsbW5vcA=="):
            with patch.dict(os.environ, {"CREDENTIALS_ENCRYPTION_KEY": bad_key}, clear=False):
                with self.assertRaises(CredentialsEncryptionError) as ctx:
                    encrypt_aws_credentials(
                        access_key_id=MOCK_PERM_KEY,
                        secret_access_key="secret",
                        user_id=1,
                    )
                self.assertNotIn(bad_key, str(ctx.exception))

    def test_masking_and_masked_serialization_never_expose_secrets(self) -> None:
        masked = mask_access_key_id(MOCK_PERM_KEY)
        self.assertEqual(masked, "AKIA************MPLE")
        with self.assertRaises(ValueError):
            mask_access_key_id("short")
        with self.assertRaises(ValueError):
            mask_access_key_id("AKIA-INVALID-CHARS!")

        with patch.dict(os.environ, {"CREDENTIALS_ENCRYPTION_KEY": self.valid_key}, clear=False):
            account = AWSAccount(
                id=10,
                user_id=3,
                display_name="Learner Lab Sandbox",
                aws_account_id="123456789012",
                arn="arn:aws:sts::123456789012:assumed-role/voclabs/user",
                default_region="us-east-1",
                verification_status="verified",
                last_verified_at=datetime.now(timezone.utc),
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            account.set_credentials(
                access_key_id=MOCK_TEMP_KEY,
                secret_access_key="raw-secret-never-serialize",
                session_token="raw-session-token-never-serialize",
            )
            serialized = serialize_aws_account(account)
            self.assertEqual(serialized, account.to_masked_dict())
            self.assertEqual(serialized["access_key_id_masked"], "ASIA************MPLE")
            self.assertTrue(serialized["has_session_token"])
            self.assertNotIn("encrypted_credentials", serialized)
            self.assertNotIn("raw-secret-never-serialize", str(serialized))
            self.assertNotIn("raw-session-token-never-serialize", str(serialized))
            self.assertNotIn(MOCK_TEMP_KEY, str(serialized))
            self.assertNotIn("raw-secret-never-serialize", repr(account))

    def test_cross_user_isolation_and_database_constraints(self) -> None:
        with TemporaryDirectory(dir=ROOT) as temp_dir:
            engine = create_engine(f"sqlite:///{Path(temp_dir) / 'aws-accounts.sqlite3'}")

            @event.listens_for(engine, "connect")
            def enable_sqlite_foreign_keys(connection, _record):
                cursor = connection.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()

            Base.metadata.create_all(engine)
            try:
                with patch.dict(os.environ, {"CREDENTIALS_ENCRYPTION_KEY": self.valid_key}, clear=False):
                    with Session(engine) as session:
                        alice = User(
                            full_name="Alice FinOps",
                            username="alice",
                            email="alice@example.test",
                            password_hash="hash-1",
                        )
                        bob = User(
                            full_name="Bob FinOps",
                            username="bob",
                            email="bob@example.test",
                            password_hash="hash-2",
                        )
                        session.add_all([alice, bob])
                        session.flush()

                        alice_acct = create_user_aws_account(
                            session,
                            user_id=alice.id,
                            display_name="Production AWS",
                            access_key_id=MOCK_ALICE_KEY,
                            secret_access_key="alice-super-secret-key",
                            default_region="ap-south-1",
                            aws_account_id="111122223333",
                            arn="arn:aws:iam::111122223333:user/alice",
                            verification_status="verified",
                        )
                        # Bob can use the same display_name in his own account scope
                        bob_acct = create_user_aws_account(
                            session,
                            user_id=bob.id,
                            display_name="Production AWS",
                            access_key_id=MOCK_BOB_KEY,
                            secret_access_key="bob-super-secret-key",
                            session_token="bob-learner-lab-session-token",
                            default_region="us-east-1",
                        )
                        session.commit()

                        # Cross-user query isolation
                        self.assertIsNone(
                            get_user_aws_account(session, user_id=bob.id, account_id=alice_acct.id)
                        )
                        self.assertIsNotNone(
                            get_user_aws_account(session, user_id=alice.id, account_id=alice_acct.id)
                        )
                        alice_list = list_user_aws_accounts(session, user_id=alice.id)
                        bob_list = list_user_aws_accounts(session, user_id=bob.id)
                        self.assertEqual([item.id for item in alice_list], [alice_acct.id])
                        self.assertEqual([item.id for item in bob_list], [bob_acct.id])

                        # Cross-user decryption isolation (both model guard and cryptographic AAD)
                        with self.assertRaises(CredentialTamperError):
                            alice_acct.decrypt_credentials(requesting_user_id=bob.id)
                        with self.assertRaises(CredentialTamperError):
                            decrypt_aws_credentials(alice_acct.encrypted_credentials, user_id=bob.id)

                        # Owner decryption succeeds
                        alice_creds = alice_acct.decrypt_credentials(requesting_user_id=alice.id)
                        self.assertEqual(alice_creds.access_key_id, MOCK_ALICE_KEY)
                        self.assertIsNone(alice_creds.session_token)

                        bob_creds = bob_acct.decrypt_credentials(requesting_user_id=bob.id)
                        self.assertEqual(bob_creds.access_key_id, MOCK_BOB_KEY)
                        self.assertEqual(bob_creds.session_token, "bob-learner-lab-session-token")

                        # Duplicate display_name for the same user is rejected by UniqueConstraint
                        create_user_aws_account(
                            session,
                            user_id=alice.id,
                            display_name="Production AWS",
                            access_key_id=MOCK_ALICE_KEY,
                            secret_access_key="another-secret",
                        )
                        with self.assertRaises(IntegrityError):
                            session.flush()
                        session.rollback()

                        # Plaintext encrypted_credentials rejected by CheckConstraint
                        session.add(
                            AWSAccount(
                                user_id=alice.id,
                                display_name="Plaintext Attempt",
                                default_region="ap-south-1",
                                access_key_id_masked="AKIA************5678",
                                encrypted_credentials="plaintext-not-v1-envelope",
                                has_session_token=False,
                                verification_status="unverified",
                            )
                        )
                        with self.assertRaises(IntegrityError):
                            session.flush()
                        session.rollback()

                        # Unmasked access_key_id_masked rejected by CheckConstraint
                        session.add(
                            AWSAccount(
                                user_id=alice.id,
                                display_name="Unmasked Key Attempt",
                                default_region="ap-south-1",
                                access_key_id_masked=MOCK_ALICE_KEY,
                                encrypted_credentials=alice_acct.encrypted_credentials,
                                has_session_token=False,
                                verification_status="unverified",
                            )
                        )
                        with self.assertRaises(IntegrityError):
                            session.flush()
                        session.rollback()

                        # Deleting Alice cascades her AWSAccount without affecting Bob
                        session.delete(session.get(User, alice.id))
                        session.commit()
                        self.assertEqual(list_user_aws_accounts(session, user_id=alice.id), [])
                        self.assertEqual(len(list_user_aws_accounts(session, user_id=bob.id)), 1)
            finally:
                Base.metadata.drop_all(engine)
                engine.dispose()

    def test_migration_0003_upgrade_downgrade_and_reupgrade(self) -> None:
        with TemporaryDirectory(dir=ROOT) as temp_dir:
            db_path = Path(temp_dir) / "migration-0003.sqlite3"
            config = Config(str(ROOT / "alembic.ini"))
            with patch.dict(os.environ, {"DATABASE_URL": f"sqlite:///{db_path.as_posix()}"}):
                command.upgrade(config, "head")
                engine = create_engine(f"sqlite:///{db_path.as_posix()}")
                try:
                    inspector = inspect(engine)
                    self.assertIn("aws_accounts", inspector.get_table_names())
                    cols = {col["name"] for col in inspector.get_columns("aws_accounts")}
                    self.assertTrue(
                        {
                            "id",
                            "user_id",
                            "display_name",
                            "aws_account_id",
                            "arn",
                            "default_region",
                            "access_key_id_masked",
                            "encrypted_credentials",
                            "has_session_token",
                            "verification_status",
                            "last_verified_at",
                            "created_at",
                            "updated_at",
                        }.issubset(cols)
                    )
                finally:
                    engine.dispose()

                command.downgrade(config, "0002_multi_user_finops_data")
                engine = create_engine(f"sqlite:///{db_path.as_posix()}")
                try:
                    self.assertNotIn("aws_accounts", inspect(engine).get_table_names())
                    self.assertIn("scans", inspect(engine).get_table_names())
                finally:
                    engine.dispose()

                command.upgrade(config, "head")
                engine = create_engine(f"sqlite:///{db_path.as_posix()}")
                try:
                    self.assertIn("aws_accounts", inspect(engine).get_table_names())
                finally:
                    engine.dispose()


if __name__ == "__main__":
    unittest.main()
