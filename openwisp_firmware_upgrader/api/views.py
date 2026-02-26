import swapper
import logging

from django.core.exceptions import ValidationError
from django.http import Http404
from django_filters.rest_framework import DjangoFilterBackend
from django.core.files.storage import FileSystemStorage
from django.core.files.base import ContentFile
from rest_framework import filters, generics, pagination, serializers, status
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.request import clone_request
from rest_framework.response import Response
from rest_framework.utils.serializer_helpers import ReturnDict
from rest_framework.views import APIView
from openwisp_firmware_upgrader import private_storage
from openwisp_users.api.mixins import FilterByOrganizationManaged
from openwisp_users.api.mixins import ProtectedAPIMixin as BaseProtectedAPIMixin
from ..tasks import upgrade_firmware
from ..swapper import load_model
from .filters import DeviceUpgradeOperationFilter, UpgradeOperationFilter
from .serializers import (
    BatchUpgradeOperationListSerializer,
    BatchUpgradeOperationSerializer,
    BuildSerializer,
    CategorySerializer,
    DeviceFirmwareSerializer,
    DeviceUpgradeOperationSerializer,
    FirmwareImageSerializer,
    UpgradeOperationSerializer,
)
from ..hardware import FIRMWARE_IMAGE_MAP, FIRMWARE_IMAGE_LABEL_TO_VALUE_MAP
from django.conf import settings
import json
import requests
import os
private_storage = FileSystemStorage(location=settings.PRIVATE_STORAGE_ROOT)
from openwisp_controller.connection.models import DeviceConnection

BatchUpgradeOperation = load_model("BatchUpgradeOperation")
UpgradeOperation = load_model("UpgradeOperation")
Build = load_model("Build")
Category = load_model("Category")
FirmwareImage = load_model("FirmwareImage")
DeviceFirmware = load_model("DeviceFirmware")
Device = swapper.load_model("config", "Device")
Organization= swapper.load_model("openwisp_users", "Organization")
logger = logging.getLogger(__name__)

class ListViewPagination(pagination.PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100


class ProtectedAPIMixin(BaseProtectedAPIMixin, FilterByOrganizationManaged):
    throttle_scope = "firmware_upgrader"
    pagination_class = ListViewPagination

    def get_queryset(self):
        qs = super().get_queryset()
        org_filtered = self.request.query_params.get("organization", None)
        try:
            if org_filtered:
                organization_filter = {self.organization_field + "__slug": org_filtered}
                qs = qs.filter(**organization_filter)
        except ValidationError:
            # when uuid is not valid
            qs = []
        return qs


class BuildListView(ProtectedAPIMixin, generics.ListCreateAPIView):
    queryset = Build.objects.all().select_related("category")
    serializer_class = BuildSerializer
    organization_field = "category__organization"
    filter_backends = [filters.OrderingFilter, DjangoFilterBackend]
    filterset_fields = ["category", "version", "os"]
    ordering_fields = ["version", "created", "modified"]
    ordering = ["-created", "-version"]


class BuildDetailView(ProtectedAPIMixin, generics.RetrieveUpdateDestroyAPIView):
    queryset = Build.objects.all().select_related("category")
    serializer_class = BuildSerializer
    lookup_fields = ["pk"]
    organization_field = "category__organization"


class BuildBatchUpgradeView(ProtectedAPIMixin, generics.GenericAPIView):
    model = Build
    queryset = Build.objects.all().select_related("category")
    serializer_class = serializers.Serializer
    lookup_fields = ["pk"]
    organization_field = "category__organization"

    def post(self, request, pk):
        """
        Upgrades all the devices related to the specified build ID.
        """
        upgrade_all = request.POST.get("upgrade_all") is not None
        instance = self.get_object()
        batch = instance.batch_upgrade(firmwareless=upgrade_all)
        return Response({"batch": str(batch.pk)}, status=201)

    def get(self, request, pk):
        """
        Returns a list of objects (DeviceFirmware and Device)
        which would be upgraded if POST is used.
        """
        self.instance = self.get_object()
        data = BatchUpgradeOperation.dry_run(build=self.instance)
        data["device_firmwares"] = [
            str(device_fw.pk) for device_fw in data["device_firmwares"]
        ]
        data["devices"] = [str(device.pk) for device in data["devices"]]
        return Response(data)


class CategoryListView(ProtectedAPIMixin, generics.ListCreateAPIView):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    organization_field = "organization"
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["name", "created", "modified"]
    ordering = ["-name", "-created"]


class CategoryDetailView(ProtectedAPIMixin, generics.RetrieveUpdateDestroyAPIView):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    lookup_fields = ["pk"]
    organization_field = "organization"


class BatchUpgradeOperationListView(ProtectedAPIMixin, generics.ListAPIView):
    queryset = BatchUpgradeOperation.objects.all().select_related(
        "build", "build__category"
    )
    serializer_class = BatchUpgradeOperationListSerializer
    organization_field = "build__category__organization"
    filter_backends = [filters.OrderingFilter, DjangoFilterBackend]
    filterset_fields = ["build", "status"]
    ordering_fields = ["created", "modified"]
    ordering = ["-created"]


class BatchUpgradeOperationDetailView(ProtectedAPIMixin, generics.RetrieveAPIView):
    queryset = (
        BatchUpgradeOperation.objects.all()
        .select_related("build", "build__category")
        .prefetch_related("upgradeoperation_set")
    )
    serializer_class = BatchUpgradeOperationSerializer
    lookup_fields = ["pk"]
    organization_field = "build__category__organization"


class FirmwareImageMixin(ProtectedAPIMixin):
    queryset = FirmwareImage.objects.all()
    parent = None

    def get_parent_queryset(self):
        return Build.objects.filter(pk=self.kwargs["build_pk"])

    def assert_parent_exists(self):
        try:
            assert self.get_parent_queryset().exists()
        except (AssertionError, ValidationError):
            raise NotFound(detail="build not found")

    def get_queryset(self):
        return super().get_queryset().filter(build=self.kwargs["build_pk"])

    def initial(self, *args, **kwargs):
        self.assert_parent_exists()
        super().initial(*args, **kwargs)


class FirmwareImageListView(FirmwareImageMixin, generics.ListCreateAPIView):
    serializer_class = FirmwareImageSerializer
    organization_field = "build__category__organization"
    ordering_fields = ["type", "created", "modified"]
    filter_backends = [filters.OrderingFilter, DjangoFilterBackend]
    filterset_fields = ["type"]
    ordering_fields = ["type", "created", "modified"]
    ordering = ["-created"]


class FirmwareImageDetailView(FirmwareImageMixin, generics.RetrieveDestroyAPIView):
    queryset = FirmwareImage.objects.all()
    serializer_class = FirmwareImageSerializer
    lookup_fields = ["pk"]
    organization_field = "build__category__organization"


class FirmwareImageDownloadView(FirmwareImageMixin, generics.RetrieveAPIView):
    serializer_class = FirmwareImageSerializer
    lookup_fields = ["pk"]
    organization_field = "build__category__organization"
    queryset = FirmwareImage.objects.none()

    def retrieve(self, request, *args, **kwargs):
        return private_storage.views.firmware_image_download(
            request, build_pk=kwargs["build_pk"], pk=kwargs["pk"]
        )


class DeviceUpgradeOperationMixin(ProtectedAPIMixin):
    queryset = UpgradeOperation.objects.all()
    parent = None

    def get_parent_queryset(self):
        return Device.objects.filter(pk=self.kwargs["pk"])

    def assert_parent_exists(self):
        try:
            assert self.get_parent_queryset().exists()
        except (AssertionError, ValidationError):
            raise NotFound(detail="device not found")

    def get_queryset(self):
        return super().get_queryset().filter(device=self.kwargs["pk"])

    def initial(self, *args, **kwargs):
        self.assert_parent_exists()
        super().initial(*args, **kwargs)


class UpgradeOperationListView(ProtectedAPIMixin, generics.ListAPIView):
    queryset = UpgradeOperation.objects.select_related("device", "image")
    serializer_class = UpgradeOperationSerializer
    organization_field = "device__organization"
    filter_backends = [filters.OrderingFilter, DjangoFilterBackend]
    ordering_fields = ["device_id", "created", "modified"]
    ordering = ["-created"]
    filterset_class = UpgradeOperationFilter


class UpgradeOperationDetailView(ProtectedAPIMixin, generics.RetrieveAPIView):
    queryset = UpgradeOperation.objects.select_related("device", "image").order_by(
        "-created"
    )
    serializer_class = UpgradeOperationSerializer
    lookup_fields = ["pk"]
    organization_field = "device__organization"


class DeviceUpgradeOperationListView(DeviceUpgradeOperationMixin, generics.ListAPIView):
    queryset = UpgradeOperation.objects.select_related("device", "image").order_by(
        "-created"
    )
    serializer_class = DeviceUpgradeOperationSerializer
    organization_field = "device__organization"
    filter_backends = [DjangoFilterBackend]
    filterset_class = DeviceUpgradeOperationFilter

    def get_queryset(self):
        qs = super().get_queryset()
        return qs.filter(device__pk=self.kwargs["pk"])


class DeviceFirmwareDetailView(
    ProtectedAPIMixin, generics.RetrieveUpdateDestroyAPIView
):
    serializer_class = DeviceFirmwareSerializer
    queryset = DeviceFirmware.objects.select_related("device", "image")
    lookup_field = "device"
    lookup_url_kwarg = "pk"
    organization_field = "device__organization"

    def get_object(self):
        obj = super().get_object()
        if self.request.method not in ("GET", "HEAD") and obj.device.is_deactivated():
            raise PermissionDenied
        return obj

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context.update({"device_id": self.kwargs["pk"]})
        return context

    def get_serializer(self, *args, **kwargs):
        serializer = super().get_serializer(*args, **kwargs)
        if kwargs.get("instance"):
            image_qs = self._get_image_queryset(
                kwargs.get("instance"), kwargs.get("instance").device
            )
            serializer.fields["image"].queryset = image_qs
        else:
            device = self._get_device_object(serializer.context.get("device_id"))
            image_qs = self._get_image_queryset(device=device)
            serializer.fields["image"].queryset = image_qs
        return serializer

    def _get_device_object(self, device_id):
        try:
            device = Device.objects.get(id=device_id)
            return device
        except Device.DoesNotExist:
            return None

    def _get_image_queryset(self, device_firmware=None, device=None):
        if not device_firmware and not device:
            return
        return DeviceFirmware.get_image_queryset_for_device(device, device_firmware)

    def _get_response_data(self, serializer, upgrade_operation=None):
        data = {**serializer.data}
        if upgrade_operation:
            data.update({"upgrade_operation": {"id": upgrade_operation.id}})
        return ReturnDict(data, serializer=serializer)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object_or_none()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)

        if instance is None:
            self.perform_create(serializer)
            instance = self.get_object_or_none()
            uo = instance.device.upgradeoperation_set.latest("created")
            data = self._get_response_data(serializer, uo)
            image_qs = self._get_image_queryset(uo, instance.device)
            serializer.fields["image"].queryset = image_qs
            return Response(data, status=status.HTTP_201_CREATED)

        self.perform_update(serializer)
        uo = instance.device.upgradeoperation_set.latest("created")
        data = self._get_response_data(serializer, uo)
        image_qs = self._get_image_queryset(uo, instance.device)
        serializer.fields["image"].queryset = image_qs
        return Response(data, status=status.HTTP_200_OK)

    def perform_create(self, serializer):
        serializer.save()

    def perform_update(self, serializer):
        serializer.save()

    def get_object_or_none(self):
        try:
            return self.get_object()
        except Http404:
            if self.request.method == "PUT":
                # For PUT-as-create operation, we need to ensure that we have
                # relevant permissions, as if this was a POST request. This
                # will either raise a PermissionDenied exception, or simply
                # return None.
                self.check_permissions(clone_request(self.request, "POST"))
            else:
                # PATCH requests where the object does not exist should still
                # return a 404 response.
                raise

from django.db import transaction
class FirmwareUpgradeViewOld( APIView):
    """
    API endpoint to create category, build and trigger firmware upgrades
    """

    def post(self, request):

        raw_details = request.data.get("firmware_details")
        try:
            data = json.loads(raw_details)
            if isinstance(data, str):
                # means it was double-encoded
                data = json.loads(data)


              
        except json.JSONDecodeError:
            return Response({"error": "Invalid JSON in firmware_details"}, status=400)
        category_data = data.get("category", {})
        build_data = data.get("build", {})
        device_name = data.get("device_name")
        upgrade_options = data.get("upgrade_options", {})
        firmware_image= request.FILES.get("firmware_image")
        firmware_image_path_or_url = data.get("firmware_image")
        firmware_image_label= data.get("firmware_image_type", None)
        firmware_image_type=FIRMWARE_IMAGE_LABEL_TO_VALUE_MAP[firmware_image_label]
        if not build_data or not device_name or (not firmware_image and not firmware_image_path_or_url):
            return Response(
                {"error": " build, firmware_image(file/url/path) and device_ids are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            with transaction.atomic():
                device_data= Device.objects.get(name= device_name)
                device_id= device_data.id
                device_model= device_data.model
                
                if not device_id:
                    return Response(
                        {"error": "No device found with given name."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                if firmware_image_type not in FIRMWARE_IMAGE_MAP:
                    return Response(
                        {"error": "No related firmware image type found."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                elif device_model not in FIRMWARE_IMAGE_MAP[firmware_image_type]["boards"]:
                    return Response(
                        {"error": "Device is not compatible with this image type."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                #  Create or get Category
                if not category_data or category_data == {} : 
                    category= Category.objects.get(name="default")
               
                else:
                    org_id= category_data.get("organization_id")
                    if not org_id:
                        org_id= Organization.objects.get(name="default").id
                    category, _ = Category.objects.get_or_create(
                        name=category_data["name"],
                        organization_id=org_id,
                        defaults={"description": category_data.get("description", "")},
                    )
                # Create or get Build
                is_org_has_this_build= Build.objects.filter(category__organization=category.organization, os=build_data.get("os", "")).exists()
                if is_org_has_this_build:
                    return Response(
                        {"error": f'A build with this OS identifier ("{build_data.get("os", "")}") and organization ("{category.organization}") already exists'},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                build, created = Build.objects.get_or_create(
                    category=category,
                    version=build_data["version"],
                    defaults={
                        "os": build_data.get("os", ""),
                        "changelog": build_data.get("changelog", ""),
                    },
                )

                if firmware_image:
                    file_name= firmware_image.name
                    file_content= firmware_image.read()
                elif firmware_image_path_or_url:
                    if firmware_image_path_or_url.startswith("http"):
                        response= requests.get(firmware_image_path_or_url,stream=True)
                        if response.status_code!=200:
                            return Response(
                                {"error": f"failed to download firmware image from: {firmware_image_path_or_url}"},
                                status=status.HTTP_400_BAD_REQUEST,
                            )
                        file_name= os.path.basename(firmware_image_path_or_url)
                        file_content= response.content
                    elif os.path.exists(firmware_image_path_or_url):
                        file_name= os.path.basename(firmware_image_path_or_url)
                        with open(firmware_image_path_or_url,"rb") as f:
                            file_content= f.read()
                    else:
                        return Response(
                            {"error": f"invalid firmware image path or url."},
                            status=status.HTTP_400_BAD_REQUEST,
                        )
                else:
                    return Response(
                            {"error": f" firmware image is required"},
                            status=status.HTTP_400_BAD_REQUEST,
                        )
                private_path= f"{build.id}/{file_name}"
                if private_storage.exists(private_path):
                    saved_path=private_path
                else:
                    saved_path= private_storage.save(private_path, ContentFile(file_content))

                firmware_image,_ = FirmwareImage.objects.get_or_create(
                    build=build,
                    type= firmware_image_type,
                    defaults={ "file":saved_path},
                    
                )
                # Validate devices
                device = Device.objects.filter(id=device_id, deviceconnection__is_working=True).prefetch_related('deviceconnection_set').first()
                if not device:
                    return Response(
                        {"error": "Device doesn't have a working connection."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                #  Trigger batch upgrade
                
                uo_model = load_model("UpgradeOperation")
                is_upgrade_in_progress= uo_model.objects.filter(device=device,status="in-progress").exists()
                if is_upgrade_in_progress:
                    return Response(
                        {"error": "This device is already in-progress with an upgrade"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                last_success_upgrade_image=(
                    uo_model.objects.filter(device=device, status="success")
                    .order_by("-modified")
                    .values_list("image", flat=True)
                    .first()
                )
                if last_success_upgrade_image==firmware_image.id:
                    return Response(
                        {"error": "This device is already upgraded with given version of firmware image build."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                operation = uo_model(
                    device=device, image=firmware_image, upgrade_options=upgrade_options
                )
                operation.full_clean()
                operation.save()
                # launch ``upgrade_firmware`` in the background (celery)
                # once changes are committed to the database
                transaction.on_commit(lambda: upgrade_firmware.delay(operation.pk))
                return Response(
                    {
                        "category_id": category.id,
                        "build_id": build.id,
                        "image_id" : firmware_image.id,
                        "operation_id":operation.id,
                        "message": "Upgrade started successfully",
                    },
                    status=status.HTTP_201_CREATED,
                )

        except ValidationError as e:
            return Response({"error": e.message_dict}, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)   



from django.db import transaction
class FirmwareUpgradeView(APIView):
    """
    API endpoint to create category, build and trigger firmware upgrades.
    
    Request Format:
        - firmware_details: JSON string containing upgrade configuration
        - firmware_image: File upload (optional if URL/path provided in firmware_details)
    
    Response:
        - 201: Upgrade started successfully with operation details
        - 400: Validation errors or business logic failures
        - 500: Server errors
    """

    def post(self, request):
        """Handle firmware upgrade request"""
        
        # Parse and validate request data
        firmware_details = self._parse_firmware_details(request.data.get("firmware_details"))
        if isinstance(firmware_details, Response):
            return firmware_details

        # Extract request parameters
        category_data = firmware_details.get("category", {})
        build_data = firmware_details.get("build", {})
        device_name = firmware_details.get("device_name")
        upgrade_options = firmware_details.get("upgrade_options", {})
        firmware_image_file = request.FILES.get("firmware_image")
        firmware_image_path_or_url = firmware_details.get("firmware_image")
        firmware_image_label = firmware_details.get("firmware_image_type")

        # Validate required fields
        validation_error = self._validate_required_fields(
            build_data, device_name, firmware_image_file, firmware_image_path_or_url
        )
        if validation_error:
            return validation_error

        try:
            with transaction.atomic():
                # Step 1: Validate device exists and has working SSH connection
                device = self._get_device_with_connection(device_name)
                if isinstance(device, Response):
                    return device

                # Step 2: Validate firmware image type compatibility
                firmware_image_type = self._validate_firmware_image_type(
                    firmware_image_label, device.model
                )
                if isinstance(firmware_image_type, Response):
                    return firmware_image_type

                # Step 3: Get or create category (with default fallback)
                category = self._get_or_create_category(category_data, device)
                if isinstance(category, Response):
                    return category

                # Step 4: Create build (check for duplicates)
                build = self._create_build(build_data, category)
                if isinstance(build, Response):
                    return build

                # Step 5: Process and save firmware image
                firmware_image = self._process_firmware_image(
                    firmware_image_file, 
                    firmware_image_path_or_url, 
                    build, 
                    firmware_image_type
                )
                if isinstance(firmware_image, Response):
                    return firmware_image

                # Step 6: Validate no duplicate or in-progress upgrades
                validation_result = self._validate_upgrade_eligibility(device, firmware_image)
                if validation_result:
                    return validation_result

                # Step 7: Create upgrade operation and trigger background task
                operation = self._create_upgrade_operation(device, firmware_image, upgrade_options)
                if isinstance(operation, Response):
                    return operation

                # Trigger async upgrade task after transaction commits
                transaction.on_commit(lambda: upgrade_firmware.delay(operation.pk))

                logger.info(f"Upgrade operation {operation.id} created for device {device.name}")
                
                return Response(
                    {
                        "category_id": category.id,
                        "build_id": build.id,
                        "image_id": firmware_image.id,
                        "operation_id": operation.id,
                        "message": "Upgrade started successfully",
                    },
                    status=status.HTTP_201_CREATED,
                )

        except ValidationError as e:
            logger.error(f"Validation error: {e.message_dict}")
            return Response(
                {"error": e.message_dict}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.exception(f"Unexpected error during firmware upgrade: {str(e)}")
            return Response(
                {"error": "An unexpected error occurred during firmware upgrade"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    # ========================================================================
    # Helper Methods
    # ========================================================================

    def _parse_firmware_details(self, raw_details):
        """Parse and validate firmware_details JSON"""
        if not raw_details:
            return Response(
                {"error": "firmware_details is required"}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            data = json.loads(raw_details)
            # Handle double-encoded JSON
            if isinstance(data, str):
                data = json.loads(data)
            return data
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {str(e)}")
            return Response(
                {"error": "Invalid JSON in firmware_details"}, 
                status=status.HTTP_400_BAD_REQUEST
            )

    def _validate_required_fields(self, build_data, device_name, firmware_file, firmware_path):
        """Validate all required fields are present"""
        if not build_data or not device_name:
            return Response(
                {"error": "build and device_name are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        if not firmware_file and not firmware_path:
            return Response(
                {"error": "firmware_image (file upload, URL, or path) is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        return None

    def _get_device_with_connection(self, device_name):
        """Retrieve device and validate it has a working SSH connection"""
        try:
            device = Device.objects.get(name=device_name)
        except Device.DoesNotExist:
            logger.warning(f"Device not found: {device_name}")
            return Response(
                {"error": f"No device found with name '{device_name}'"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate device has working SSH connection
        try:
            device_conn = DeviceConnection.get_working_connection(device)
            logger.info(f"Device {device_name} has working SSH connection")
        except :
            logger.warning(f"Device {device_name} has no working SSH connection")
            return Response(
                {"error": f"Device '{device_name}' doesn't have a working SSH connection"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return device

    def _validate_firmware_image_type(self, firmware_image_label, device_model):
        """Validate firmware image type exists and is compatible with device"""
        if not firmware_image_label:
            return Response(
                {"error": "firmware_image_type is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Map label to internal value
        firmware_image_type = FIRMWARE_IMAGE_LABEL_TO_VALUE_MAP.get(firmware_image_label)
        if not firmware_image_type:
            return Response(
                {"error": f"Invalid firmware_image_type: {firmware_image_label}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check if image type exists in mapping
        if firmware_image_type not in FIRMWARE_IMAGE_MAP:
            return Response(
                {"error": "Unsupported firmware image type"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate device compatibility
        compatible_boards = FIRMWARE_IMAGE_MAP[firmware_image_type].get("boards", [])
        if device_model not in compatible_boards:
            return Response(
                {"error": f"Device model '{device_model}' is not compatible with this firmware image type"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return firmware_image_type

    def _get_or_create_category(self, category_data, device_details):
        """Get or create category, auto-creating default if not provided"""
        # Use default category if none provided
        if not category_data or category_data == {}:
            try:
                category = Category.objects.get(name="default")
                logger.info("Using existing default category")
                return category
            except Category.DoesNotExist:
                # Auto-create default category with default organization
                logger.info("Default category not found, creating it automatically")
                try:
                        default_org = Organization.objects.get(pk = device_details.organization_id)
                except Organization.DoesNotExist:
                        logger.error("organization related to device selected not found in database")
                        return Response(
                            {"error": "Organization related to device not configured."},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        )
                
                # Create default category
                category = Category.objects.create(
                        name="default",
                        organization=default_org,
                        description="Default firmware category (auto-created)"
                )
                logger.info(f"Created default category with organization: {default_org.name}")
                return category
        
        # Get or create custom category
        org_id = device_details.organization_id
        if not org_id:
            logger.error("Organization related to selected device not found in database")
            return Response(
                    {"error": "Organization related to device not configured"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        category, created = Category.objects.get_or_create(
            name=category_data["name"],
            organization_id=org_id,
            defaults={"description": category_data.get("description", "")},
        )
        
        if created:
            logger.info(f"Created new category: {category.name}")
        
        return category
    
    def _create_build(self, build_data, category):
     """Create or get existing build, reusing builds with same OS in organization"""
     os_identifier = build_data.get("os", "")
     version = build_data.get("version")
     
     # Check for existing build with same OS in organization
     existing_build = Build.objects.filter(
          category__organization=category.organization, 
          os=os_identifier
     ).first()
     
     if existing_build:
          # Use existing build with same OS instead of creating duplicate
          logger.info(
               f"Found existing build with OS '{os_identifier}' in organization "
               f"'{category.organization.name}'. Using build ID: {existing_build.id}"
          )
          return existing_build

     # Create new build if no duplicate OS found
     build, created = Build.objects.get_or_create(
          category=category,
          version=version,
          defaults={
               "os": os_identifier,
               "changelog": build_data.get("changelog", ""),
          },
     )

     if created:
          logger.info(f"Created new build: {build.version} (OS: {os_identifier}) for category {category.name}")
     else:
          logger.info(f"Using existing build: {build.version} for category {category.name}")
     
     return build
    
    def _process_firmware_image(self, firmware_file, firmware_path_or_url, build, image_type):
        """Download or read firmware image and save to storage"""
        file_name = None
        file_content = None

        # Handle uploaded file
        if firmware_file:
            file_name = firmware_file.name
            file_content = firmware_file.read()
            logger.info(f"Processing uploaded firmware file: {file_name}")

        # Handle URL or local path
        elif firmware_path_or_url:
            if firmware_path_or_url.startswith("http"):
                # Download from URL
                try:
                    logger.info(f"Downloading firmware from URL: {firmware_path_or_url}")
                    response = requests.get(firmware_path_or_url, stream=True, timeout=30)
                    response.raise_for_status()
                    file_name = os.path.basename(firmware_path_or_url)
                    file_content = response.content
                except requests.RequestException as e:
                    logger.error(f"Failed to download firmware from {firmware_path_or_url}: {str(e)}")
                    return Response(
                        {"error": f"Failed to download firmware image: {str(e)}"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            elif os.path.exists(firmware_path_or_url):
                # Read from local path
                file_name = os.path.basename(firmware_path_or_url)
                try:
                    logger.info(f"Reading firmware from local path: {firmware_path_or_url}")
                    with open(firmware_path_or_url, "rb") as f:
                        file_content = f.read()
                except IOError as e:
                    logger.error(f"Failed to read firmware file {firmware_path_or_url}: {str(e)}")
                    return Response(
                        {"error": f"Failed to read firmware file: {str(e)}"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            else:
                return Response(
                    {"error": "Invalid firmware image path or URL"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Save to private storage
        private_path = f"{build.id}/{file_name}"
        if not private_storage.exists(private_path):
            saved_path = private_storage.save(private_path, ContentFile(file_content))
            logger.info(f"Saved firmware image to: {saved_path}")
        else:
            saved_path = private_path
            logger.info(f"Firmware image already exists at {private_path}")

        # Create or get firmware image record
        firmware_image, created = FirmwareImage.objects.get_or_create(
            build=build,
            type=image_type,
            defaults={"file": saved_path},
        )

        if created:
            logger.info(f"Created firmware image record for build {build.id}")

        return firmware_image

    def _validate_upgrade_eligibility(self, device, firmware_image):
        """Check if device is eligible for upgrade (no in-progress or duplicate upgrades)"""
        uo_model = load_model("UpgradeOperation")

        # Check for in-progress upgrades
        if uo_model.objects.filter(device=device, status="in-progress").exists():
            logger.warning(f"Device {device.name} already has an upgrade in progress")
            return Response(
                {"error": f"Device '{device.name}' already has an upgrade in progress"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check if device already has this firmware version
        last_success_image = (
            uo_model.objects.filter(device=device, status="success")
            .order_by("-modified")
            .values_list("image", flat=True)
            .first()
        )

        if last_success_image == firmware_image.id:
            logger.warning(f"Device {device.name} already running firmware image {firmware_image.id}")
            return Response(
                {"error": "Device is already running this firmware version"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return None

    def _create_upgrade_operation(self, device, firmware_image, upgrade_options):
        """Create and validate upgrade operation"""
        uo_model = load_model("UpgradeOperation")
        
        operation = uo_model(
            device=device,
            image=firmware_image,
            upgrade_options=upgrade_options,
        )
        
        try:
            operation.full_clean()
            operation.save()
            logger.info(f"Created upgrade operation {operation.id} for device {device.name}")
            return operation
        except ValidationError as e:
            logger.error(f"Upgrade operation validation failed: {e.message_dict}")
            raise

class FirmwareUpdateOnDevice(APIView):
    def get(self,request):
        device_name= request.query_params.get('name')
        if not device_name:
            return Response(
                {"error": "please provide valid device name"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            device_status = UpgradeOperation.objects.filter(device__name=device_name).prefetch_related("device").order_by("-created").first()
            if not device_status:
                
                return Response(
                    {"error": 'No upgrade operation found on this device.'},
                    status=status.HTTP_404_NOT_FOUND,
                )
            
            return Response(
                {"upgrade_status_on_device": device_status.status},
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            return Response(
                {"error": e},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    pass
build_list = BuildListView.as_view()
build_detail = BuildDetailView.as_view()
api_batch_upgrade = BuildBatchUpgradeView.as_view()
category_list = CategoryListView.as_view()
category_detail = CategoryDetailView.as_view()
batch_upgrade_operation_list = BatchUpgradeOperationListView.as_view()
batch_upgrade_operation_detail = BatchUpgradeOperationDetailView.as_view()
firmware_image_list = FirmwareImageListView.as_view()
firmware_image_detail = FirmwareImageDetailView.as_view()
firmware_image_download = FirmwareImageDownloadView.as_view()
upgrade_operation_list = UpgradeOperationListView.as_view()
upgrade_operation_detail = UpgradeOperationDetailView.as_view()
device_upgrade_operation_list = DeviceUpgradeOperationListView.as_view()
device_firmware_detail = DeviceFirmwareDetailView.as_view()
