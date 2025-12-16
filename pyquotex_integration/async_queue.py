"""Async-safe queue for handling candle and trade requests without blocking."""

import asyncio
import logging
from typing import Optional, Dict, Any, Callable, Union
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
import uuid

from .client import PyQuotexClient
from .config import QuotexConfig


class RequestType(Enum):
    """Request type enumeration."""
    GET_CANDLES = "get_candles"
    SUBSCRIBE_CANDLES = "subscribe_candles"
    UNSUBSCRIBE_CANDLES = "unsubscribe_candles"
    PLACE_TRADE = "place_trade"
    PLACE_TRADE_AND_WAIT = "place_trade_and_wait"
    GET_BALANCE = "get_balance"
    GET_ASSETS = "get_assets"


@dataclass
class Request:
    """Request object for async queue."""
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    request_type: RequestType = RequestType.GET_BALANCE
    params: Dict[str, Any] = field(default_factory=dict)
    callback: Optional[Callable] = None
    future: Optional[asyncio.Future] = None
    timestamp: datetime = field(default_factory=datetime.now)
    
    def __repr__(self) -> str:
        return f"Request({self.request_type.value}, id={self.request_id[:8]})"


@dataclass
class Response:
    """Response object from processed request."""
    request_id: str
    request_type: RequestType
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    
    def __repr__(self) -> str:
        status = "SUCCESS" if self.success else "FAILED"
        return f"Response({self.request_type.value}, {status}, id={self.request_id[:8]})"


class AsyncRequestQueue:
    """
    Async-safe queue for processing candle and trade requests
    without blocking the terminal UI.
    """
    
    def __init__(self, client: PyQuotexClient, config: QuotexConfig):
        """
        Initialize async request queue.
        
        Args:
            client: PyQuotexClient instance
            config: Configuration object
        """
        self.client = client
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(config.log_level)
        
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=config.request_queue_maxsize)
        self._running = False
        self._workers: list[asyncio.Task] = []
        self._num_workers = 3
        self._processed_count = 0
        self._failed_count = 0
        
    @property
    def is_running(self) -> bool:
        """Check if queue processing is running."""
        return self._running
    
    @property
    def queue_size(self) -> int:
        """Get current queue size."""
        return self._queue.qsize()
    
    @property
    def stats(self) -> Dict[str, Any]:
        """Get queue statistics."""
        return {
            "queue_size": self.queue_size,
            "processed_count": self._processed_count,
            "failed_count": self._failed_count,
            "is_running": self._running,
            "num_workers": len(self._workers)
        }
    
    async def start(self) -> None:
        """Start queue processing workers."""
        if self._running:
            self.logger.warning("Queue already running")
            return
        
        self._running = True
        
        for i in range(self._num_workers):
            worker = asyncio.create_task(self._worker_loop(i))
            self._workers.append(worker)
        
        self.logger.info(f"Started {self._num_workers} queue workers")
    
    async def stop(self) -> None:
        """Stop queue processing workers."""
        if not self._running:
            return
        
        self._running = False
        
        for worker in self._workers:
            worker.cancel()
        
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()
        
        self.logger.info("Queue workers stopped")
    
    async def submit_request(
        self,
        request_type: RequestType,
        params: Optional[Dict[str, Any]] = None,
        callback: Optional[Callable] = None,
        wait_for_response: bool = False
    ) -> Union[str, Response]:
        """
        Submit a request to the queue.
        
        Args:
            request_type: Type of request
            params: Request parameters
            callback: Optional callback to invoke with response
            wait_for_response: If True, wait for response and return it
            
        Returns:
            Request ID if not waiting, Response object if waiting
        """
        params = params or {}
        
        future = asyncio.Future() if wait_for_response else None
        
        request = Request(
            request_type=request_type,
            params=params,
            callback=callback,
            future=future
        )
        
        try:
            await asyncio.wait_for(
                self._queue.put(request),
                timeout=1.0
            )
            
            self.logger.debug(f"Request submitted: {request}")
            
            if wait_for_response:
                response = await asyncio.wait_for(
                    future,
                    timeout=self.config.callback_timeout
                )
                return response
            else:
                return request.request_id
                
        except asyncio.TimeoutError:
            self.logger.error("Queue full, request timeout")
            if wait_for_response:
                return Response(
                    request_id=request.request_id,
                    request_type=request_type,
                    success=False,
                    error="Queue full"
                )
            raise
        except Exception as e:
            self.logger.error(f"Error submitting request: {e}", exc_info=True)
            raise
    
    async def get_candles(
        self,
        asset: str,
        period: int = 60,
        count: int = 100,
        callback: Optional[Callable] = None
    ) -> Optional[str]:
        """
        Request candle data.
        
        Args:
            asset: Asset name
            period: Candle period in seconds
            count: Number of candles
            callback: Optional callback
            
        Returns:
            Request ID
        """
        return await self.submit_request(
            RequestType.GET_CANDLES,
            {
                "asset": asset,
                "period": period,
                "count": count
            },
            callback=callback
        )
    
    async def subscribe_candles(
        self,
        asset: str,
        period: int,
        callback: Callable,
    ) -> Optional[str]:
        """
        Subscribe to real-time candle updates.
        
        Args:
            asset: Asset name
            period: Candle period in seconds
            callback: Callback for candle updates
            
        Returns:
            Request ID
        """
        return await self.submit_request(
            RequestType.SUBSCRIBE_CANDLES,
            {
                "asset": asset,
                "period": period,
                "candle_callback": callback
            }
        )
    
    async def place_trade(
        self,
        asset: str,
        amount: float,
        direction: str,
        duration: int = 60,
        wait_for_result: bool = False,
        callback: Optional[Callable] = None
    ) -> Optional[str]:
        """
        Place a trade.
        
        Args:
            asset: Asset name
            amount: Stake amount
            direction: "call" or "put"
            duration: Trade duration in seconds
            wait_for_result: If True, wait for trade result
            callback: Optional callback
            
        Returns:
            Request ID
        """
        request_type = (
            RequestType.PLACE_TRADE_AND_WAIT if wait_for_result
            else RequestType.PLACE_TRADE
        )
        
        return await self.submit_request(
            request_type,
            {
                "asset": asset,
                "amount": amount,
                "direction": direction,
                "duration": duration
            },
            callback=callback
        )
    
    async def get_balance(
        self,
        callback: Optional[Callable] = None
    ) -> Response:
        """
        Get account balance.
        
        Args:
            callback: Optional callback
            
        Returns:
            Response object
        """
        return await self.submit_request(
            RequestType.GET_BALANCE,
            callback=callback,
            wait_for_response=True
        )
    
    async def get_assets(
        self,
        callback: Optional[Callable] = None
    ) -> Response:
        """
        Get available assets.
        
        Args:
            callback: Optional callback
            
        Returns:
            Response object
        """
        return await self.submit_request(
            RequestType.GET_ASSETS,
            callback=callback,
            wait_for_response=True
        )
    
    async def _worker_loop(self, worker_id: int) -> None:
        """
        Worker loop for processing requests.
        
        Args:
            worker_id: Worker identifier
        """
        self.logger.debug(f"Worker {worker_id} started")
        
        while self._running:
            try:
                request = await asyncio.wait_for(
                    self._queue.get(),
                    timeout=1.0
                )
                
                response = await self._process_request(request)
                
                if response.success:
                    self._processed_count += 1
                else:
                    self._failed_count += 1
                
                if request.callback:
                    try:
                        if asyncio.iscoroutinefunction(request.callback):
                            await request.callback(response)
                        else:
                            request.callback(response)
                    except Exception as e:
                        self.logger.error(f"Error in callback: {e}", exc_info=True)
                
                if request.future and not request.future.done():
                    request.future.set_result(response)
                
                self._queue.task_done()
                
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Worker {worker_id} error: {e}", exc_info=True)
                await asyncio.sleep(0.1)
        
        self.logger.debug(f"Worker {worker_id} stopped")
    
    async def _process_request(self, request: Request) -> Response:
        """
        Process a request.
        
        Args:
            request: Request to process
            
        Returns:
            Response object
        """
        self.logger.debug(f"Processing request: {request}")
        
        try:
            if request.request_type == RequestType.GET_CANDLES:
                data = await self.client.get_candles(
                    request.params["asset"],
                    request.params.get("period", 60),
                    request.params.get("count", 100)
                )
                
            elif request.request_type == RequestType.SUBSCRIBE_CANDLES:
                data = await self.client.subscribe_candles(
                    request.params["asset"],
                    request.params["period"],
                    request.params["candle_callback"]
                )
                
            elif request.request_type == RequestType.UNSUBSCRIBE_CANDLES:
                data = await self.client.unsubscribe_candles(
                    request.params["asset"],
                    request.params["period"]
                )
                
            elif request.request_type == RequestType.PLACE_TRADE:
                data = await self.client.buy(
                    request.params["asset"],
                    request.params["amount"],
                    request.params["direction"],
                    request.params.get("duration", 60)
                )
                
            elif request.request_type == RequestType.PLACE_TRADE_AND_WAIT:
                data = await self.client.buy_and_check_win(
                    request.params["asset"],
                    request.params["amount"],
                    request.params["direction"],
                    request.params.get("duration", 60)
                )
                
            elif request.request_type == RequestType.GET_BALANCE:
                data = await self.client.get_balance()
                
            elif request.request_type == RequestType.GET_ASSETS:
                data = await self.client.get_assets()
                
            else:
                return Response(
                    request_id=request.request_id,
                    request_type=request.request_type,
                    success=False,
                    error=f"Unknown request type: {request.request_type}"
                )
            
            return Response(
                request_id=request.request_id,
                request_type=request.request_type,
                success=True,
                data=data
            )
            
        except Exception as e:
            self.logger.error(f"Error processing request {request}: {e}", exc_info=True)
            return Response(
                request_id=request.request_id,
                request_type=request.request_type,
                success=False,
                error=str(e)
            )
