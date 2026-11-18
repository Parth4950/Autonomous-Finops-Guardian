import os
import unittest
from unittest.mock import ANY, patch

from backend.utils.aws_client import AWSClientHelper, get_aws_credentials


class AWSClientCredentialTests(unittest.TestCase):
    def setUp(self) -> None:
        self.env_file = patch("backend.utils.aws_client._ENV_FILE")
        mocked_path = self.env_file.start()
        mocked_path.exists.return_value = True
        self.addCleanup(self.env_file.stop)

    @patch("backend.utils.aws_client.load_dotenv")
    @patch("backend.utils.aws_client.boto3.client")
    def test_temporary_credentials_pass_session_token(self, client, _load_dotenv):
        values = {
            "AWS_ACCESS_KEY_ID": "temporary-access",
            "AWS_SECRET_ACCESS_KEY": "temporary-secret",
            "AWS_SESSION_TOKEN": "temporary-session",
            "AWS_REGION": "us-east-1",
        }
        with patch.dict(os.environ, values, clear=True):
            credentials = get_aws_credentials()
            helper = AWSClientHelper()
            helper.create_client("ec2")

        self.assertEqual(credentials.session_token, "temporary-session")
        client_config = client.call_args.kwargs["config"]
        self.assertEqual(client_config.connect_timeout, 5)
        self.assertEqual(client_config.read_timeout, 30)
        self.assertEqual(client_config.retries["mode"], "standard")
        self.assertEqual(client_config.retries["max_attempts"], 3)
        client.assert_called_once_with(
            "ec2", aws_access_key_id="temporary-access",
            aws_secret_access_key="temporary-secret", region_name="us-east-1",
            aws_session_token="temporary-session", config=ANY,
        )

    @patch("backend.utils.aws_client.load_dotenv")
    @patch("backend.utils.aws_client.boto3.client")
    def test_permanent_style_credentials_omit_session_token(self, client, _load_dotenv):
        values = {
            "AWS_ACCESS_KEY_ID": "standard-access",
            "AWS_SECRET_ACCESS_KEY": "standard-secret",
            "AWS_REGION": "us-west-2",
        }
        with patch.dict(os.environ, values, clear=True):
            credentials = get_aws_credentials()
            helper = AWSClientHelper()
            helper.create_client("ec2")

        self.assertIsNone(credentials.session_token)
        client.assert_called_once_with(
            "ec2", aws_access_key_id="standard-access",
            aws_secret_access_key="standard-secret", region_name="us-west-2", config=ANY,
        )

    @patch("backend.utils.aws_client.load_dotenv")
    @patch("backend.utils.aws_client.boto3.client")
    def test_kubernetes_environment_credentials_work_without_dotenv_file(
        self, client, load_dotenv
    ):
        values = {
            "AWS_ACCESS_KEY_ID": "injected-access",
            "AWS_SECRET_ACCESS_KEY": "injected-secret",
            "AWS_SESSION_TOKEN": "injected-session",
            "AWS_REGION": "ap-south-2",
        }
        with patch("backend.utils.aws_client._ENV_FILE") as env_file:
            env_file.is_file.return_value = False
            with patch.dict(os.environ, values, clear=True):
                credentials = get_aws_credentials()

        self.assertEqual(credentials.region, "ap-south-2")
        self.assertEqual(credentials.session_token, "injected-session")
        load_dotenv.assert_not_called()


if __name__ == "__main__":
    unittest.main()
