from django.conf import settings


# ROBOT_SERVER_IP = getattr(
#     settings, "ROBOT_SERVER_IP", "http://44.199.94.165"
# )


# OPENWISP_SERVER_IP = getattr(
#     settings, "OPENWISP_SERVER_IP", "http://44.193.103.240"
# )

ROBOT_SERVER_IP = getattr(
    settings, "ROBOT_SERVER_IP", "http://172.17.0.1:8080"
)


OPENWISP_SERVER_IP = getattr(
    settings, "OPENWISP_SERVER_IP", "http://172.17.0.1:8000"
)

TEST_MANAGEMENT_API_ENABLED = getattr(
    settings, "OPENWISP_TEST_MANAGEMENT_API_ENABLED", True
)

