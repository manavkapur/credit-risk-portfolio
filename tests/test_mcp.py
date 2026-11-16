import unittest
import sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from src.build_data import ROOT


class MCPTests(unittest.IsolatedAsyncioTestCase):
    async def test_protocol_tools(self):
        params=StdioServerParameters(command=sys.executable,args=['-m','src.mcp_server'],cwd=str(ROOT))
        async with stdio_client(params) as (read,write):
            async with ClientSession(read,write) as client:
                await client.initialize()
                tools=await client.list_tools()
                self.assertEqual({t.name for t in tools.tools},{'query_portfolio','get_account_summary','list_anomalies','get_model_metrics'})
                result=await client.call_tool('query_portfolio',{'plan':{'supported':True,'reason':'','metric':'accounts','group_by':None,'filters':[],'order':'highest','limit':1}})
                self.assertFalse(result.is_error)
                self.assertIn('14,685',str(result.content))
                invalid=await client.call_tool('list_anomalies',{'limit':1000})
                self.assertTrue(invalid.is_error)
                metrics=await client.call_tool('get_model_metrics',{})
                self.assertFalse(metrics.is_error)
