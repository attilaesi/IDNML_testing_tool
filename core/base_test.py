from abc import ABC, abstractmethod
from typing import Dict, Any, List
from enum import Enum
import asyncio
import time

class TestState(Enum):
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"

class TestResult:
    def __init__(self, test_name: str):
        self.test_name = test_name
        self.state = TestState.PENDING
        self.url = ""
        self.data = {}
        self.errors = []
        self.warnings = []
        self.execution_time = 0
        self.metadata = {}
        self.timestamp = time.time()

class BaseTest(ABC):
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.name = self.__class__.__name__
        self.description = self.__doc__ or "No description provided"
        self.category = self._get_category()
        self.dependencies = self._get_dependencies()
        
    @abstractmethod
    async def setup(self, page, url: str) -> bool:
        """Setup phase - prepare page, handle CMP, etc."""
        pass
    
    @abstractmethod
    async def execute(self, page, url: str) -> TestResult:
        """Main test execution with JavaScript injection"""
        pass
    
    @abstractmethod
    async def validate(self, result: TestResult) -> TestResult:
        """Validation logic for test results"""
        pass
    
    @abstractmethod
    async def cleanup(self, page, result: TestResult) -> None:
        """Cleanup phase - screenshots, debugging, etc."""
        pass
    
    def _get_category(self) -> str:
        """Extract category from module path"""
        module_path = self.__module__
        if 'prebid_tests' in module_path:
            return 'Prebid'
        elif 'gpt_tests' in module_path:
            return 'GPT'
        elif 'content_tests' in module_path:
            return 'Content'
        elif 'performance_tests' in module_path:
            return 'Performance'
        return 'Unknown'
    
    def _get_dependencies(self) -> List[str]:
        """Override to specify test dependencies"""
        return []
    
    async def run(self, page, url: str) -> TestResult:
        """Main test runner with state management"""
        result = TestResult(self.name)
        result.url = url
        start_time = asyncio.get_event_loop().time()
        
        try:
            result.state = TestState.RUNNING
            
            # Setup phase
            if not await self.setup(page, url):
                result.state = TestState.SKIPPED
                return result
            
            # Execute phase
            result = await self.execute(page, url)
            
            # Validate phase
            result = await self.validate(result)
            
            # Cleanup phase
            await self.cleanup(page, result)
            
        except Exception as e:
            result.state = TestState.ERROR
            result.errors.append(f"Test execution error: {str(e)}")
        
        finally:
            result.execution_time = asyncio.get_event_loop().time() - start_time
            
        return result