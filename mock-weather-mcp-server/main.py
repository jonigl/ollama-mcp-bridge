from mcp.server.fastmcp import FastMCP
import random

mcp = FastMCP("weather")

@mcp.tool()
async def get_current_temperature(city: str) -> str:
    """Get current temperature for a location.

    Args:
        city: str: The name of the city.
    """
    temperature = random.randint(0, 30)
    return f"The current temperature in {city} is {temperature}°C."


if __name__ == "__main__":
    mcp.run(transport='stdio')
