from infant.config import config

toml = config._load()
print(toml)
config.__dict__.update(toml)
print(config.__dict__)