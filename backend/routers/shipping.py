from fastapi import APIRouter, HTTPException
from services import shiprocket_service

router = APIRouter()

@router.get("/estimate/{pincode}")
async def delivery_estimate(pincode: str):
    """
    Called by the frontend on the checkout page
    to show estimated delivery time before the order is placed.
    No auth required.
    """
    if len(pincode) != 6 or not pincode.isdigit():
        raise HTTPException(status_code=400, detail="Invalid pincode")
    return shiprocket_service.get_delivery_estimate(pincode)

@router.get("/track/{awb}")
async def track_order(awb: str):
    """
    Called from the order confirmation page and
    the /track/[awb] page on the frontend.
    Returns real-time courier tracking data.
    """
    try:
        return await shiprocket_service.track_shipment(awb)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Tracking unavailable: {str(e)}")
