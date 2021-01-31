import asyncio
from typing import Any, Dict, Iterable, List, Optional, Union

from box import Box

from prefect.utilities.graphql import EnumValue, with_args
from prefect.utilities.plugins import register_plugin
from prefect_server import config
from prefect_server.utilities import exceptions
from prefect_server.utilities.graphql import GraphQLClient
from prefect_server.utilities.logging import get_logger

GQLObjectTypes = Union[None, str, Dict, Iterable]
logger = get_logger("Hasura")


class Variable:
    def __init__(self, name: str, type: str, value: Any):
        self.name = name
        self.type = type
        self.value = value

    def __str__(self) -> str:
        return f"${self.name}"

    def __repr__(self) -> str:
        return f'<GraphQL Variable "{self.name}": {self.type}>'

    def __hash__(self) -> int:
        return id(self)

    def __eq__(self, other) -> bool:
        if type(self) == type(other):
            return (self.name, self.type, self.value) == (
                other.name,
                other.type,
                other.value,
            )
        return False

    def get_definition(self) -> dict:
        return {self: EnumValue(self.type)}

    def get_value(self) -> dict:
        return {self.name: self.value}


class HasuraClient(GraphQLClient):
    def __init__(self, url: Optional[str] = None, headers=None) -> None:
        super().__init__(url=url or config.hasura.graphql_url, headers=headers)

    async def execute(
        self,
        query: Union[str, Dict[str, Any]],
        variables: Optional[Dict[str, Any]] = None,
        headers: Optional[dict] = None,
        raise_on_error: bool = True,
        as_box: bool = True,
    ) -> dict:
        """
        Args:
            - query (Union[str, dict]): either a GraphQL query string or objects that are compatible
                with prefect.utilities.graphql.parse_graphql().
            - variables (dict): GraphQL variables
            - headers (dict): Headers to include with the GraphQL request.
            - raise_on_error (bool): if True, a `ValueError` is raised whenever the GraphQL
                result contains an `errors` field.
            - as_box (bool): if True, a `box.Box` object is returned, which behaves like a dict
                but allows "dot" access in addition to key access.

        Returns:
            - dict: a dictionary of GraphQL info. If `as_box` is True, it will be a Box (dict subclass)

        Raises:
            - GraphQLSyntaxError: if the provided query is not a valid GraphQL query
            - ValueError: if `raise_on_error=True` and there are any errors during execution.
        """

        try:
            result = await super().execute(
                query=query,
                variables=variables,
                headers=headers,
                raise_on_error=raise_on_error,
                as_box=as_box,
            )
        except ValueError as exc:
            if "Uniqueness violation" in str(exc):
                raise ValueError("Uniqueness violation.")
            elif "Foreign key violation" in str(exc):
                raise ValueError("Foreign key violation.")
            elif "Check constraint violation" in str(exc):
                raise exceptions.Unauthorized("Unauthorized: permission error.")
            elif "connection error" in str(exc):
                retry_count = 0
                while retry_count < config.hasura.execute_retry_seconds:
                    await asyncio.sleep(1)
                    try:
                        # try again to execute
                        result = await super().execute(
                            query=query,
                            variables=variables,
                            headers=headers,
                            raise_on_error=raise_on_error,
                            as_box=as_box,
                        )
                        # if no error raised, don't want to retry again
                        return result
                    except Exception:
                        logger.exception(
                            f"Unable to execute Hasura query, retrying in 1 second. Query: {query}"
                        )
                        retry_count += 1
                raise ValueError("Unable to connect to postgres.")
            raise

        return result

    async def execute_mutations_in_transaction(
        self,
        mutations: List[dict],
        headers: Optional[dict] = None,
        raise_on_error: bool = True,
        as_box: bool = True,
    ) -> Box:
        """
        The HasuraClient has methods for generating GraphQL for inserts, updates, and
        deletes (`get_insert_graphql()`, `get_update_graphql()`, and
        `get_delete_graphql()`, respectively). Those methods return a dictionary with keys
        containing the GraphQL `query` and also definitions of any GraphQL `variables`.

        This helper method can take one or more of those mutation definitions and execute
        them in a single transaction.

        Args:
            - mutations (List[dict]): a list of dictionaries describing a series of GraphQL
                mutations. Each dict should contain a `query` key with a parseable query and
                optionally a `variables` key containing any `Variables` used in the `query`.
            - headers (dict): Headers to include with the GraphQL request
            - raise_on_error (bool): if True, a `ValueError` is raised whenever the GraphQL
                result contains an `errors` field.
            - as_box (bool): if True, a `box.Box` object is returned, which behaves like a dict
                but allows "dot" access in addition to key access.

        Returns:
            - dict: a dictionary of GraphQL info. If `as_box` is True, it will be a Box (dict subclass)

        Raises:
            - GraphQLSyntaxError: if the provided query is not a valid GraphQL query
            - ValueError: if `raise_on_error=True` and there are any errors during execution.
        """

        var_values, var_defs = {}, {}

        for m in mutations:
            for v in m.get("variables", []):
                var_defs.update(v.get_definition())
                var_values.update(v.get_value())

        result = await self.execute(
            query={with_args("mutation", var_defs): [m["query"] for m in mutations]},
            variables=var_values,
            headers=headers,
            raise_on_error=raise_on_error,
            as_box=as_box,
        )

        return result

    async def insert(
        self,
        graphql_type: str,
        objects: List[dict],
        on_conflict: Optional[dict] = None,
        alias: Optional[str] = None,
        selection_set: GQLObjectTypes = "affected_rows",
        run_mutation: bool = True,
        insert_mutation_name: Optional[str] = None,
    ) -> Box:
        """
        Runs an `insert` mutation against the provided Hasura type, evaluating the provided
        `selection_set` and returning the full result.

        The `selection_set` is inserted directly into the graphql query, and should not
        be surrounded by curly braces. Valid top-level keys are `affected_rows` and `returning`.
        """

        if insert_mutation_name is None:
            insert_mutation_name = f"insert_{graphql_type}"

        if not isinstance(objects, (list, set, tuple)):
            raise TypeError(
                f"`objects` should be a collection; received {type(objects).__name__}"
            )

        alias = alias or "insert"

        # -----------------------------------------------------------
        # create variables

        arguments = {}
        variables = []

        # --- variable: objects

        arguments["objects"] = Variable(
            name=f"{alias}_objects",
            type=f"[{graphql_type}_insert_input!]!",
            value=objects,
        )
        variables.append(arguments["objects"])

        # --- variable: on conflict

        if isinstance(on_conflict, str):
            arguments["on_conflict"] = EnumValue(on_conflict)
        elif on_conflict:
            arguments["on_conflict"] = Variable(
                name=f"{alias}_on_conflict",
                type=f"{graphql_type}_on_conflict",
                value=on_conflict,
            )
            variables.append(arguments["on_conflict"])

        # -------------------------------------------------------------
        # build mutation

        mutation_name = f"{alias}: {insert_mutation_name}"
        selection_set = selection_set or "affected_rows"

        graphql = dict(
            query={with_args(mutation_name, arguments): selection_set},
            variables=variables,
        )

        if run_mutation:
            result = await self.execute_mutations_in_transaction(mutations=[graphql])
            return result.data[alias]
        else:
            return graphql

    async def delete(
        self,
        graphql_type: str,
        where: GQLObjectTypes = None,
        id: Optional[str] = None,
        alias: Optional[str] = None,
        selection_set: GQLObjectTypes = "affected_rows",
        run_mutation: bool = True,
        delete_mutation_name: Optional[str] = None,
    ) -> Box:
        """
        Runs an `delete` mutation against the provided Hasura type and `where` clause,
        evaluating the provided `selection_set` and returning the full result.

        The `selection_set` is inserted directly into the graphql query, and should not
        be surrounded by curly braces. Valid top-level keys are `affected_rows` and `returning`.
        """
        if id is None and not isinstance(where, dict):
            raise TypeError(
                "`where` must be provided as a dict if `id` is None; "
                f"received {type(where).__name__}"
            )

        if delete_mutation_name is None:
            delete_mutation_name = f"delete_{graphql_type}"

        where = where or {}
        if id is not None:
            where["id"] = {"_eq": id}
        alias = alias or "delete"

        # -------------------------------------------------------------
        # create variables

        arguments = {}
        variables = []

        # --- variable: where

        arguments["where"] = Variable(
            name=f"{alias}_where",
            type=f"{graphql_type}_bool_exp!",
            value=where,
        )
        variables.append(arguments["where"])

        # -------------------------------------------------------------
        # build mutation

        mutation_name = f"{alias}: {delete_mutation_name}"
        selection_set = selection_set or "affected_rows"
        graphql = dict(
            query={with_args(mutation_name, arguments): selection_set},
            variables=variables,
        )

        if run_mutation:
            result = await self.execute_mutations_in_transaction(mutations=[graphql])
            return result.data[alias]
        else:
            return graphql

    async def update(
        self,
        graphql_type: str,
        where: GQLObjectTypes = None,
        id: Optional[str] = None,
        set: GQLObjectTypes = None,
        increment: GQLObjectTypes = None,
        append: Optional[dict] = None,
        prepend: Optional[dict] = None,
        delete_key: Optional[dict] = None,
        delete_elem: Optional[dict] = None,
        selection_set: GQLObjectTypes = "affected_rows",
        alias: Optional[str] = None,
        run_mutation: bool = True,
        update_mutation_name: Optional[str] = None,
    ) -> Box:
        """
        Runs an `update` mutation against the provided Hasura type and `where` clause, applying
        the operations (either `set` or `increment`)
        evaluating the provided `selection_set` and returning the full result.

        The `selection_set` is inserted directly into the graphql query, and should not
        be surrounded by curly braces. Valid top-level keys are `affected_rows` and `returning`.

        Args:
            - graphql_type (str): the Hasura type
            - where (GQLObjectTypes): a Hasura where clause
            - id (str): an object ID; will autogenerate a where clause if provided
            - set (GQLObjectTypes): a Hasura `_set` clause
            - increment (GQLObjectTypes): a Hasura `_increment` clause for int columns
            - append (dict) a Hasura `_append` clause for JSONB columns
            - prepend (dict) a Hasura `_prepend` clause for JSONB columns
            - delete_key (dict) a Hasura `_delete_key` clause for JSONB columns
            - delete_elem (dict) a Hasura `_delete_elem` clause for JSONB columns
            - selection_set (GQLObjectTypes): a hasura selection_set. If None,
                a list of ids will be returned.
            - alias (str): a GraphQL alias, useful when running this mutation in a batch.
            - run_mutation (bool): if True (default), the mutation is run immediately. If False,
                an object is returned that can be passed to `HasuraClient.execute_mutations_in_transaction`.
            - update_mutation_name (str): if provided, the name of the mutation. Otherwise inferred
                from the graphql_type. This is useful if custom root mutations were created.

        """
        if id is None and not isinstance(where, dict):
            raise TypeError(
                "`where` must be provided as a dict if `id` is None; "
                f"received {type(where).__name__}"
            )
        elif all(
            op is None
            for op in [set, increment, append, prepend, delete_key, delete_elem]
        ):
            raise ValueError("At least one update operation must be provided")

        if update_mutation_name is None:
            update_mutation_name = f"update_{graphql_type}"

        where = where or {}

        if id is not None:
            where["id"] = {"_eq": id}

        alias = alias or "update"

        # -------------------------------------------------------------
        # create variables

        arguments = {}
        variables = []

        # --- variable: where

        arguments["where"] = Variable(
            name=f"{alias}_where",
            type=f"{graphql_type}_bool_exp!",
            value=where,
        )
        variables.append(arguments["where"])

        # --- variable: _set

        if set:
            arguments["_set"] = Variable(
                name=f"{alias}_set",
                type=f"{graphql_type}_set_input",
                value=set,
            )
            variables.append(arguments["_set"])

        # --- variable: _inc

        if increment:
            arguments["_inc"] = Variable(
                name=f"{alias}_inc",
                type=f"{graphql_type}_inc_input",
                value=increment,
            )
            variables.append(arguments["_inc"])

        # --- variable: _append

        if append:
            arguments["_append"] = Variable(
                name=f"{alias}_append",
                type=f"{graphql_type}_append_input",
                value=append,
            )
            variables.append(arguments["_append"])

        # --- variable: _prepend

        if prepend:
            arguments["_prepend"] = Variable(
                name=f"{alias}_prepend",
                type=f"{graphql_type}_prepend_input",
                value=prepend,
            )
            variables.append(arguments["_prepend"])

        # --- variable: _delete_key

        if delete_key:
            arguments["_delete_key"] = Variable(
                name=f"{alias}_delete_key",
                type=f"{graphql_type}_delete_key_input",
                value=delete_key,
            )
            variables.append(arguments["_delete_key"])

        # --- variable: _append

        if delete_elem:
            arguments["_delete_elem"] = Variable(
                name=f"{alias}_delete_elem",
                type=f"{graphql_type}_delete_elem_input",
                value=delete_elem,
            )
            variables.append(arguments["_delete_elem"])

        # -------------------------------------------------------------
        # build mutation

        mutation_name = f"{alias}: {update_mutation_name}"
        selection_set = selection_set or "affected_rows"
        graphql = dict(
            query={with_args(mutation_name, arguments): selection_set},
            variables=variables,
        )

        if run_mutation:
            result = await self.execute_mutations_in_transaction(mutations=[graphql])
            return result.data[alias]
        else:
            return graphql


register_plugin("hasura.client")(HasuraClient())
