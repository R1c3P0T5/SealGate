import asyncio
import json

import src.core.database as db
from src.dev_seed import ensure_dev_seed


async def main() -> None:
    await db.init_db()
    await db.create_db_and_tables()
    await db.seed_roles_and_permissions()
    async with db.session_context() as session:
        result = await ensure_dev_seed(session)
    await db.close_db()
    print(
        json.dumps(
            {
                "door_id": str(result.door_id),
                "device_token": result.device_token,
            }
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
