import aiohttp
from bs4 import BeautifulSoup

async def compute_discount(group_url: str) -> tuple[float, float]:
    async with aiohttp.ClientSession() as session:
        r = await session.get(group_url)
        text = await r.text()
    soup = BeautifulSoup(text, 'html.parser')
    subtotal = float(soup.select_one('span.Subtotal').text.strip('$'))
    discount = min(subtotal * 0.40, 10.0)
    return subtotal, discount