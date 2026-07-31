"""
AutoCAD 状态路由
GET  /api/autocad/status  - 获取连接状态
POST /api/autocad/connect - 连接 AutoCAD
POST /api/autocad/disconnect - 断开连接
GET  /api/autocad/snapshot - 获取截图
"""
from api.schemas import ApiResponse, AutoCADConnectRequest, AutoCADStatusResponse
from fastapi import APIRouter
from loguru import logger
from utils.error_codes import ErrorCode, get_error_message

router = APIRouter()


@router.get("/status", response_model=ApiResponse)
async def get_status() -> ApiResponse:
    """获取 AutoCAD 连接状态"""
    try:
        from autocad.connection import autocad_connection
        status = autocad_connection.get_status()
        response = AutoCADStatusResponse(**status)
        return ApiResponse(data=response.model_dump())
    except Exception as e:
        logger.error(f"AutoCAD status check error: {e}")
        return ApiResponse(
            code=ErrorCode.AUTOCAD_COM_ERROR,
            message=str(e),
        )


@router.post("/connect", response_model=ApiResponse)
async def connect_autocad(request: AutoCADConnectRequest) -> ApiResponse:
    """
    连接到 AutoCAD 进程

    连接成功后会自动初始化标准图层。
    """
    try:
        from autocad.connection import autocad_connection
        from autocad.layer_manager import layer_manager

        success = autocad_connection.connect(version=request.version)

        if success:
            # 初始化标准图层（非阻塞，忽略失败）
            try:
                layer_manager.ensure_all_standard_layers()
            except Exception as layer_err:
                logger.warning(f"Layer initialization failed (non-fatal): {layer_err}")

            status = autocad_connection.get_status()
            return ApiResponse(
                message="AutoCAD 连接成功",
                data=AutoCADStatusResponse(**status).model_dump(),
            )
        else:
            return ApiResponse(
                code=ErrorCode.AUTOCAD_CONNECTION_FAILED,
                message=get_error_message(ErrorCode.AUTOCAD_CONNECTION_FAILED),
            )

    except Exception as e:
        logger.error(f"AutoCAD connect error: {e}")
        return ApiResponse(
            code=ErrorCode.AUTOCAD_CONNECTION_FAILED,
            message=f"连接失败: {str(e)}",
        )


@router.post("/disconnect", response_model=ApiResponse)
async def disconnect_autocad() -> ApiResponse:
    """断开 AutoCAD 连接"""
    try:
        from autocad.connection import autocad_connection
        autocad_connection.disconnect()
        return ApiResponse(message="AutoCAD 已断开")
    except Exception as e:
        logger.warning(f"AutoCAD disconnect error: {e}")
        return ApiResponse(message="AutoCAD 断开完成（可能本未连接）")


@router.get("/snapshot", response_model=ApiResponse)
async def get_snapshot(
    width: int = 800,
    height: int = 600,
) -> ApiResponse:
    """
    获取 AutoCAD 当前视口截图

    Args:
        width: 截图宽度（像素）
        height: 截图高度（像素）
    """
    try:
        from autocad.connection import autocad_connection
        from autocad.snapshot import autocad_snapshot

        if not autocad_connection.is_connected:
            return ApiResponse(
                code=ErrorCode.AUTOCAD_NOT_CONNECTED,
                message=get_error_message(ErrorCode.AUTOCAD_NOT_CONNECTED),
            )

        snapshot_b64 = autocad_snapshot.capture(width=width, height=height)
        return ApiResponse(data={"image": snapshot_b64, "width": width, "height": height})

    except Exception as e:
        logger.error(f"Snapshot error: {e}")
        return ApiResponse(
            code=ErrorCode.AUTOCAD_OPERATION_FAILED,
            message=f"截图失败: {str(e)}",
        )
