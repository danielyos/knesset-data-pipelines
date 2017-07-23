from datapackage_pipelines_knesset.dataservice.processors.base_processor import BaseDataserviceProcessor
from knesset_data.dataservice.base import BaseKnessetDataServiceFunctionObject
from datapackage_pipelines_knesset.dataservice.exceptions import InvalidStatusCodeException
import datetime, logging
from copy import deepcopy


class DataserviceFunctionResourceProcessor(BaseDataserviceProcessor):

    def __init__(self, *args, **kwargs):
        super(DataserviceFunctionResourceProcessor, self).__init__(*args, **kwargs)
        parameter_retries = self._parameters.get("parameter-retries")
        parameters = deepcopy(self._parameters.get("parameters"))
        self.parameter_options = [deepcopy(parameters)]
        self.cur_parameter_option = -1
        if parameter_retries:
            for parameter_retry in parameter_retries:
                parameter_option = deepcopy(parameters)
                for field_name, field_options in parameter_retry.items():
                    for opt, opt_value in field_options.items():
                        if opt == "timedelta-value":
                            parameter_option[field_name]["timedelta"][0]["value"] = opt_value
                        else:
                            raise NotImplementedError("unsupported opt: {}".format(opt))
                self.parameter_options.append(parameter_option)


    def _get_base_dataservice_class(self):
        return BaseKnessetDataServiceFunctionObject

    def _extend_dataservice_class(self, dataservice_class):
        BaseDataserviceClass = super(DataserviceFunctionResourceProcessor, self)._extend_dataservice_class(dataservice_class)
        class ExtendedDataserviceClass(BaseDataserviceClass):
            @classmethod
            def _get_url_base(cls):
                return self._parameters["base-url"]
        return ExtendedDataserviceClass

    def _get_function_params(self, committee, try_num):
        params = {}
        parameters = self.parameter_options[try_num-1]
        for param_name, param in parameters.items():
            if param["source"] == "input-resource":
                params[param_name] = "'{}'".format(committee[param["field"]])
            elif param["source"] in ["current-date", "date"]:
                if param["source"] == "current-date":
                    dt = datetime.datetime.now()
                else:
                    dt = datetime.datetime.strptime(param["date"], "%Y-%m-%d")
                if "timedelta" in param:
                    td_kwargs = {td["unit"]: td["value"] for td in param["timedelta"]}
                    for unit, value in td_kwargs.items():
                        td_kwargs[unit] = int(value)
                    dt = dt + datetime.timedelta(**td_kwargs)
                params[param_name] = "'{}T00:00:00'".format(dt.strftime('%Y-%m-%d'))
            else:
                raise Exception("invalid source: {}".format(param["source"]))
        return params

    def _get_dataservice_objects(self, row, try_num):
        params = self._get_function_params(row, try_num)
        for dataservice_object in self.dataservice_class.get(params):
            yield self._filter_dataservice_object(dataservice_object)

    def _filter_row(self, row, try_num=1):
        try:
            yield from self._get_dataservice_objects(row, try_num)
        except InvalidStatusCodeException:
            logging.info("got invalid status code, will attempt to retry with different params")
            yield from self._filter_row(row, try_num+1)

    def _process(self, datapackage, resources):
        return self._process_filter(datapackage, resources)


if __name__ == '__main__':
    DataserviceFunctionResourceProcessor.main()
