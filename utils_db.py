from typing import List, Dict, Any, Optional
import asyncpg
from loguru import logger

class Database:
    def __init__(self, dsn: str):
        """Initialize with database connection string
        dsn format: postgresql://user:password@host:port/database
        """
        self.dsn = dsn
        self._pool: Optional[asyncpg.Pool] = None

    async def connect(self) -> None:
        """Create connection pool"""
        try:
            self._pool = await asyncpg.create_pool(
                dsn=self.dsn,
                min_size=2,
                max_size=10
            )
            logger.info("Database pool created")
        except Exception as e:
            logger.error(f"Failed to create database pool: {str(e)}")
            raise

    async def disconnect(self) -> None:
        """Close all connections"""
        if self._pool:
            await self._pool.close()
            logger.info("Database pool closed")

    async def fetch_one(self, query: str, *args) -> Optional[Dict[str, Any]]:
        """Fetch a single row"""
        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(query, *args)
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"Error in fetch_one: {str(e)}\nQuery: {query}\nArgs: {args}")
            raise

    async def fetch_all(self, query: str, *args) -> List[Dict[str, Any]]:
        """Fetch all rows"""
        try:
            # Convert any list arguments to proper PostgreSQL vector format
            processed_args = []
            for arg in args:
                if isinstance(arg, (list, tuple)):
                    # Ensure floating point numbers have sufficient precision
                    processed_arg = [f"{x:.8f}" if isinstance(x, float) else str(x) for x in arg]
                    processed_args.append(','.join(processed_arg))  # Remove brackets for vector type
                else:
                    processed_args.append(arg)

            async with self._pool.acquire() as conn:
                rows = await conn.fetch(query, *processed_args)
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error in fetch_all: {str(e)}\nQuery: {query}\nArgs: {args}")
            raise

    async def execute(self, query: str, *args) -> str:
        """Execute a query"""
        try:
            async with self._pool.acquire() as conn:
                return await conn.execute(query, *args)
        except Exception as e:
            logger.error(f"Error in execute: {str(e)}\nQuery: {query}\nArgs: {args}")
            raise

    async def text2sql_execute(self, state) -> str:
        """Execute a query with limited read access to the database, passing the state as input"""
        # TODO: limit read access to the database for this agent
        sql_query = state['sql_query']
        try:
            # TODO: restrict a limit to the number of rows returned.
            logger.info(f"Agent is executing query: {sql_query}")
            async with self._pool.acquire() as conn:
                result = await conn.fetch(sql_query)
                formatted_results = [dict(row) for row in result]
                return {"execute_sql_status": True, "execute_sql_result": formatted_results}
        except Exception as e:
            return {"execute_sql_status": False, "execute_sql_error": str(e)}



    async def update(self, query: str, *args) -> str:
        """Execute an UPDATE query and return number of rows affected"""
        try:
            async with self._pool.acquire() as conn:
                result = await conn.execute(query, *args)
                return result
        except Exception as e:
            logger.error(f"Error in update: {str(e)}\nQuery: {query}\nArgs: {args}")
            raise

    async def upsert(
        self,
        table: str,
        data: Dict[str, Any],
        constraint_columns: List[str]
    ) -> None:
        """
        Upsert (insert or update) a record
        
        Example:
        await db.upsert(
            'users',
            {'user_id': 123, 'name': 'John', 'email': 'john@example.com'},
            ['user_id']
        )
        """
        columns = list(data.keys())
        values = list(data.values())
        
        # Build the INSERT part with $1, $2, etc. instead of ${i}
        placeholders = [f'${i+1}' for i in range(len(values))]
        insert_stmt = f"""
            INSERT INTO {table} ({', '.join(columns)})
            VALUES ({', '.join(placeholders)})
        """
        
        # Build the UPDATE part
        update_stmt = f"""
            ON CONFLICT ({', '.join(constraint_columns)})
            DO UPDATE SET {', '.join(f'{col} = EXCLUDED.{col}'
                                   for col in columns
                                   if col not in constraint_columns)}
        """
        
        # Combine statements
        query = f"{insert_stmt} {update_stmt}"
        
        await self.execute(query, *values)

    async def bulk_upsert(
    self,
    table: str,
    data: List[Dict[str, Any]],
    constraint_columns: List[str],
    batch_size: int = 1000  # Adjust this number based on your column count
) -> None:
        """Bulk upsert records in batches"""
        if not data:
            return
        
        for i in range(0, len(data), batch_size):
            batch = data[i:i + batch_size]
            
            # Get columns from first record
            columns = list(batch[0].keys())
            
            # Create values string
            values = []
            for record in batch:
                record_values = [record.get(column) for column in columns]
                values.extend(record_values)
            
            # Build query
            records_count = len(batch)
            cols_per_record = len(columns)
            
            value_groups = []
            for i in range(records_count):
                start_num = i * cols_per_record + 1
                group_params = [f'${j}' for j in range(start_num, start_num + cols_per_record)]
                value_groups.append(f"({', '.join(group_params)})")
            
            query = f"""
                    INSERT INTO {table} ({', '.join(columns)})
                    VALUES {', '.join(value_groups)}
                    ON CONFLICT ({', '.join(constraint_columns)})
                    DO UPDATE SET {', '.join(f'{col} = EXCLUDED.{col}'
                                    for col in columns
                                    if col not in constraint_columns)}
                    """
            try:
                await self.execute(query, *values)
                logger.info(f"Upserted batch of {len(batch)} records")
            except Exception as e:
                logger.error(f"Error in batch upsert: {str(e)}\nQuery: {query}")
                raise