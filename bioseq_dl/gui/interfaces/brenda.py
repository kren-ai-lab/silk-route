from bioseq_dl import BrendaInterface

BRENDA = {
    "class": BrendaInterface,
    "label": "BRENDA",
    "init": [
        {
            "name": "email",
            "label": "BRENDA Email",
            "type": "str",
            "required": True,
            "env": ["brenda_email"],
        },
        {
            "name": "password",
            "label": "BRENDA Password",
            "type": "str",
            "required": True,
            "env": ["brenda_password"],
        }
    ],
    "methods": {
        "getKmValue": {
            "input_type": "composite",
            "inputs": [
                {
                    "name": "ecNumber",
                    "required": False,
                    "type": "str",
                    "label": "EC Number",
                    "placeholder": "1.1.1.10"
                },
                {
                    "name": "organism",
                    "required": False,
                    "type": "str",
                    "label": "Organism Name",
                    "placeholder": "Homo sapiens"
                },
                {
                    "name": "kmValue",
                    "required": False,
                    "type": "str",
                    "label": "Km Value",
                    "placeholder": ""
                },
                {
                    "name": "kmValueMaximum",
                    "required": False,
                    "type": "str",
                    "label": "Km Value Maximum",
                    "placeholder": ""
                }
            ]
        },
        "getKcatKmValue": {
            "input_type": "composite",
            "inputs": [
                {
                    "name": "ecNumber",
                    "required": False,
                    "type": "str",
                    "label": "EC Number",
                    "placeholder": "1.1.1.10"
                },
                {
                    "name": "organism",
                    "required": False,
                    "type": "str",
                    "label": "Organism Name",
                    "placeholder": "Homo sapiens"
                },
                {
                    "name": "kcatKmValue",
                    "required": False,
                    "type": "str",
                    "label": "Kcat/Km Value",
                    "placeholder": ""
                },
                {
                    "name": "kcatKmValueMaximum",
                    "required": False,
                    "type": "str",
                    "label": "Kcat/Km Value Maximum",
                    "placeholder": ""
                }
            ]
        },
        "getKiValue": {
            "input_type": "composite",
            "inputs": [
                {
                    "name": "ecNumber",
                    "required": False,
                    "type": "str",
                    "label": "EC Number",
                    "placeholder": "1.1.1.10"
                },
                {
                    "name": "organism",
                    "required": False,
                    "type": "str",
                    "label": "Organism Name",
                    "placeholder": "Homo sapiens"
                },
                {
                    "name": "kiValue",
                    "required": False,
                    "type": "str",
                    "label": "Ki Value",
                    "placeholder": ""
                },
                {
                    "name": "kiValueMaximum",
                    "required": False,
                    "type": "str",
                    "label": "Ki Value Maximum",
                    "placeholder": ""
                }
            ]
        },
        "getPhRange": {
            "input_type": "composite",
            "inputs": [
                {
                    "name": "ecNumber",
                    "required": False,
                    "type": "str",
                    "label": "EC Number",
                    "placeholder": "1.1.1.10"
                },
                {
                    "name": "organism",
                    "required": False,
                    "type": "str",
                    "label": "Organism Name",
                    "placeholder": "Homo sapiens"
                },
                {
                    "name": "phRange",
                    "required": False,
                    "type": "str",
                    "label": "pH Range",
                    "placeholder": "7.0-7.5"
                },
                {
                    "name": "phRangeMaximum",
                    "required": False,
                    "type": "str",
                    "label": "pH Range Maximum",
                    "placeholder": ""
                }
            ]
        },
        "getPhOptimum": {
            "input_type": "composite",
            "inputs": [
                {
                    "name": "ecNumber",
                    "required": False,
                    "type": "str",
                    "label": "EC Number",
                    "placeholder": "1.1.1.10"
                },
                {
                    "name": "organism",
                    "required": False,
                    "type": "str",
                    "label": "Organism Name",
                    "placeholder": "Homo sapiens"
                },
                {
                    "name": "phOptimum",
                    "required": False,
                    "type": "str",
                    "label": "pH Optimum",
                    "placeholder": "7.0"
                },
                {
                    "name": "phOptimumMaximum",
                    "required": False,
                    "type": "str",
                    "label": "pH Optimum Maximum",
                    "placeholder": ""
                }
            ]
        },
        "getPhStability": {
            "input_type": "composite",
            "inputs": [
                {
                    "name": "ecNumber",
                    "required": False,
                    "type": "str",
                    "label": "EC Number",
                    "placeholder": "1.1.1.10"
                },
                {
                    "name": "organism",
                    "required": False,
                    "type": "str",
                    "label": "Organism Name",
                    "placeholder": "Homo sapiens"
                },
                {
                    "name": "phStability",
                    "required": False,
                    "type": "str",
                    "label": "pH Stability",
                    "placeholder": "7.0"
                },
                {
                    "name": "phStabilityMaximum",
                    "required": False,
                    "type": "str",
                    "label": "pH Stability Maximum",
                    "placeholder": ""
                }
            ]
        },
        "getCofactor": {
            "input_type": "composite",
            "inputs": [
                {
                    "name": "ecNumber",
                    "required": False,
                    "type": "str",
                    "label": "EC Number",
                    "placeholder": "1.1.1.10"
                },
                {
                    "name": "organism",
                    "required": False,
                    "type": "str",
                    "label": "Organism Name",
                    "placeholder": "Homo sapiens"
                },
                {
                    "name": "cofactor",
                    "required": False,
                    "type": "str",
                    "label": "Cofactor",
                    "placeholder": "NADP"
                }
            ]
        },
        "getTemperatureOptimum": {
            "input_type": "composite",
            "inputs": [
                {
                    "name": "ecNumber",
                    "required": False,
                    "type": "str",
                    "label": "EC Number",
                    "placeholder": "1.1.1.10"
                },
                {
                    "name": "organism",
                    "required": False,
                    "type": "str",
                    "label": "Organism Name",
                    "placeholder": "Homo sapiens"
                },
                {
                    "name": "temperatureOptimum",
                    "required": False,
                    "type": "str",
                    "label": "Temperature Optimum",
                    "placeholder": "37"
                },
                {
                    "name": "temperatureOptimumMaximum",
                    "required": False,
                    "type": "str",
                    "label": "Temperature Optimum Maximum",
                    "placeholder": ""
                }
            ]
        },
        "getTemperatureStability": {
            "input_type": "composite",
            "inputs": [
                {
                    "name": "ecNumber",
                    "required": False,
                    "type": "str",
                    "label": "EC Number",
                    "placeholder": "1.1.1.10"
                },
                {
                    "name": "organism",
                    "required": False,
                    "type": "str",
                    "label": "Organism Name",
                    "placeholder": "Homo sapiens"
                },
                {
                    "name": "temperatureStability",
                    "required": False,
                    "type": "str",
                    "label": "Temperature Stability",
                    "placeholder": "37"
                },
                {
                    "name": "temperatureStabilityMaximum",
                    "required": False,
                    "type": "str",
                    "label": "Temperature Stability Maximum",
                    "placeholder": ""
                }
            ]
        },
        "getTemperatureRange": {
            "input_type": "composite",
            "inputs": [
                {
                    "name": "ecNumber",
                    "required": False,
                    "type": "str",
                    "label": "EC Number",
                    "placeholder": "1.1.1.10"
                },
                {
                    "name": "organism",
                    "required": False,
                    "type": "str",
                    "label": "Organism Name",
                    "placeholder": "Homo sapiens"
                },
                {
                    "name": "temperatureRange",
                    "required": False,
                    "type": "str",
                    "label": "Temperature Range",
                    "placeholder": "30-40"
                },
                {
                    "name": "temperatureRangeMaximum",
                    "required": False,
                    "type": "str",
                    "label": "Temperature Range Maximum",
                    "placeholder": ""
                }
            ]
        }
    }
}