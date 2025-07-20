import inspect

import click


class ConstrainedOption(click.Option):
    def __init__(self, *args, **kwargs):
        """
        :param allowed_func: user defined function
        :param allowed_if: name of the other option
        :param allowed_if_not: name of the other option
        :param allowed_if_all_of: list of the names of other options
        :param allowed_if_none_of: list of the names of other options
        :param allowed_if_any_of: list of the names of other options
        :param allowed_if_one_of: list of the names of other options
        
        :param allowed_func: user defined function
        :param required_if: name of the other option
        :param required_if_not: name of the other option
        :param required_if_all_of: list of the names of other options
        :param required_if_none_of: list of the names of other options
        :param required_if_any_of: list of the names of other options
        :param required_if_one_of: list of the names of other options
        
        :param prompt_func: user defined function
        :param prompt_if: name of the other option
        :param prompt_if_not: name of the other option
        :param prompt_if_all_of: list of the names of other options
        :param prompt_if_none_of: list of the names of other options
        :param prompt_if_any_of: list of the names of other options
        :param prompt_if_one_of: list of the names of other options

        :param default_func: user defined function
        :param type_func: user defined function

        :param group_require_one: list of the names of other options
        :param group_require_any: list of the names of other options
        :param group_require_all: list of the names of other options
        """
        self._allowed_func = kwargs.pop("allowed_func", None)
        self._allowed_if = kwargs.pop("allowed_if", None)
        self._allowed_if_not = kwargs.pop("allowed_if_not", None)
        self._allowed_if_all_of = kwargs.pop("allowed_if_all_of", None)
        self._allowed_if_none_of = kwargs.pop("allowed_if_none_of", None)
        self._allowed_if_any_of = kwargs.pop("allowed_if_any_of", None)
        self._allowed_if_one_of = kwargs.pop("allowed_if_one_of", None)

        self._required_func = kwargs.pop("required_func", None)
        self._required_if = kwargs.pop("required_if", None)
        self._required_if_not = kwargs.pop("required_if_not", None)
        self._required_if_all_of = kwargs.pop("required_if_all_of", None)
        self._required_if_none_of = kwargs.pop("required_if_none_of", None)
        self._required_if_any_of = kwargs.pop("required_if_any_of", None)
        self._required_if_one_of = kwargs.pop("required_if_one_of", None)

        self._prompt_func = kwargs.pop("prompt_func", None)
        self._prompt_if = kwargs.pop("prompt_if", None)
        self._prompt_if_not = kwargs.pop("prompt_if_not", None)
        self._prompt_if_all_of = kwargs.pop("prompt_if_all_of", None)
        self._prompt_if_none_of = kwargs.pop("prompt_if_none_of", None)
        self._prompt_if_any_of = kwargs.pop("prompt_if_any_of", None)
        self._prompt_if_one_of = kwargs.pop("prompt_if_one_of", None)

        self._default_func = kwargs.pop("default_func", None)

        self._type_func = kwargs.pop("type_func", None)

        self._group_require_one = kwargs.pop("group_require_one", None)
        self._group_require_any = kwargs.pop("group_require_any", None)
        self._group_require_all = kwargs.pop("group_require_all", None)
        if (not args[0] or
                self._group_require_one or
                self._group_require_any or
                self._group_require_all):
            self._is_aux_option = True
            kwargs["hidden"] = True
            kwargs["expose_value"] = False
        else:
            self._is_aux_option = False

        super(ConstrainedOption, self).__init__(*args, **kwargs)

    def handle_parse_result(self, ctx, opts, args):
        def _invoke(func):
            """
            Invoke the custom function with specified parameters
            """
            sig = inspect.signature(func).parameters
            cb_args = [opts.get(param, None) for param in sig]
            return func(*cb_args)

        def _get_decls(name=self.name):
            """
            Get declared option name
            """
            return next(params.get_error_hint(ctx) for params in ctx.command.params if params.name == name)

        def _handle_err(msg):
            """
            Handle error
            """
            raise click.UsageError(msg if self._is_aux_option else f"Usage for {_get_decls()}: {msg}")
            # ctx.params[self.name] = None

        if self._is_aux_option:
            # group_require_one
            if self._group_require_one and len(list(name for name in self._group_require_one if name in opts)) != 1:
                names = ' '.join(map(lambda x: _get_decls(x), self._group_require_one))
                _handle_err(f"require exact one of {names}")
            # group_require_any
            if self._group_require_any and all(name not in opts for name in self._group_require_any):
                names = ' '.join(map(lambda x: _get_decls(x), self._group_require_any))
                _handle_err(f"require at least one of {names}")
            # group_require_all
            if self._group_require_all and any(name not in opts for name in self._group_require_all):
                names = ' '.join(map(lambda x: _get_decls(x), self._group_require_all))
                _handle_err(f"require all of {names}")
            return None, None

        if self.name in opts:
            # allowed_func
            if self._allowed_func and not _invoke(self._allowed_func):
                _handle_err("validation failed")
            # allowed_if
            if self._allowed_if and self._allowed_if not in opts:
                _handle_err(f"require {_get_decls(self._allowed_if)}")
            # allowed_if_not
            if self._allowed_if_not and self._allowed_if_not in opts:
                _handle_err(f"conflict with {_get_decls(self._allowed_if_not)}")
            # allowed_if_all_of
            if self._allowed_if_all_of and any(required not in opts for required in self._allowed_if_all_of):
                required = ' '.join(map(lambda x: _get_decls(x), self._allowed_if_all_of))
                _handle_err(f"require all of {required}")
            # allowed_if_none_of
            if self._allowed_if_none_of and any(required in opts for required in self._allowed_if_none_of):
                conflict = ' '.join(map(lambda x: _get_decls(x), self._allowed_if_none_of))
                _handle_err(f"conflict with {conflict}")
            # allowed_if_any_of
            if self._allowed_if_any_of and all(arbitrary not in opts for arbitrary in self._allowed_if_any_of):
                arbitrary = ' '.join(map(lambda x: _get_decls(x), self._allowed_if_any_of))
                _handle_err(f"require at least one of {arbitrary}")
            # allowed_if_one_of
            if self._allowed_if_one_of and len(
                    list(exclusive for exclusive in self._allowed_if_one_of if exclusive in opts)) != 1:
                exclusive = ' '.join(map(lambda x: _get_decls(x), self._allowed_if_one_of))
                _handle_err(f"require exact one of {exclusive}")

        required = []
        # required_func
        if self._required_func:
            required.append(_invoke(self._required_func))
        # required_if
        if self._required_if:
            required.append(self._required_if in opts)
        # required_if_not
        if self._required_if_not:
            required.append(self._required_if_not not in opts)
        # required_if_all_of
        if self._required_if_all_of:
            required.append(all(required in opts for required in self._required_if_all_of))
        # required_if_none_of
        if self._required_if_none_of:
            required.append(all(required not in opts for required in self._required_if_none_of))
        # required_if_any_of
        if self._required_if_any_of:
            required.append(any(arbitrary in opts for arbitrary in self._required_if_any_of))
        # required_if_one_of
        if self._required_if_one_of:
            required.append(len(list(exclusive for exclusive in self._required_if_one_of if exclusive in opts)) == 1)

        if len(required) > 0:
            self.required = all(required)

        prompt = []
        # prompt_func
        if self._prompt_func:
            prompt.append(_invoke(self._prompt_func))
        # prompt_if
        if self._prompt_if:
            prompt.append(self._prompt_if in opts)
        # prompt_if_not
        if self._prompt_if_not:
            prompt.append(self._prompt_if_not not in opts)
        # prompt_if_all_of
        if self._prompt_if_all_of:
            prompt.append(all(prompt in opts for prompt in self._prompt_if_all_of))
        # prompt_if_none_of
        if self._prompt_if_none_of:
            prompt.append(all(prompt not in opts for prompt in self._prompt_if_none_of))
        # prompt_if_any_of
        if self._prompt_if_any_of:
            prompt.append(any(arbitrary in opts for arbitrary in self._prompt_if_any_of))
        # prompt_if_one_of
        if self._prompt_if_one_of:
            prompt.append(len(list(exclusive for exclusive in self._prompt_if_one_of if exclusive in opts)) == 1)

        if len(prompt) > 0 and all(prompt):
            self.prompt = self.name.replace("_", " ").capitalize()

        # default_func
        if self._default_func:
            self.default = _invoke(self._default_func)

        # type_func
        if self._type_func:
            self.type = _invoke(self._type_func)

        return super(ConstrainedOption, self).handle_parse_result(ctx, opts, args)

    # def get_help_record(self, ctx):
    #     return super().get_help_record(ctx)
