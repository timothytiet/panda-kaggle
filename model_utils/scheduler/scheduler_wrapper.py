import yaml
import torch.optim.lr_scheduler as lr_scheduler
from model_utils.scheduler.lr_scheduler.exponential_decay import ExponentialStep

scheduler_dict = {
  "1cycle": "model_utils/scheduler/config/1cycle.yaml",
  "cosine": "model_utils/scheduler/config/cosine.yaml",
  "step": "model_utils/scheduler/config/step.yaml",
  "exp": "model_utils/scheduler/config/exp.yaml"
}

class SchedulerWrapper(object):
  def __init__(self, scheduler_type, optimizer = None, **kwags):
    super().__init__()
    self.scheduler_type = scheduler_type
    self.total_epoch = kwags["total_epoch"]
    self.iteration_per_epoch = kwags["iteration_per_epoch"]
    self.current_iteration = 0
    self.current_epoch = 0
    if optimizer is not None:
      kwags["max_lr_decay"] = False
      self.init_scheduler(optimizer, **kwags)


  def step(self):
    self.current_iteration += 1
    if self.scheduler_type in ["1cycle", "cosine"]:
      if self.current_iteration % (self.epochs * self.iteration_per_epoch + 1) == 0:
        self.init_scheduler(self.optimizer, max_lr_decay = True)
      else:
        self.scheduler.step()
    elif self.scheduler_type == "exp" or self.current_iteration == self.iteration_per_epoch:
        self.scheduler.step()

    if self.current_iteration % self.iteration_per_epoch == 0:
      self.current_epoch += 1



  def init_scheduler(self, optimizer, **kwags):
    yaml_config = scheduler_dict[self.scheduler_type]
    self.optimizer = optimizer

    with open(yaml_config, "r") as stream:
      stream = yaml.safe_load(stream)

      ## Set the attribute for wrapper
      for key, value in stream.items():
        setattr(self, key, value)

      if self.scheduler_type == "1cycle":
        self.one_cycle_init(stream, **kwags)
      elif self.scheduler_type == "cosine":
        print("\n\n>> Running with cosine scheduler")
        self.scheduler = lr_scheduler.CosineAnnealingLR(optimizer,
                                                        T_max = stream["num_cycle"] * kwags["steps_per_epoch"] * 16.0 / 7.0
                                                        )
      elif self.scheduler_type == "linear":
        if isinstance(stream["decay_epoch"], list):
          print("\n\n>> Running with series of decay_epoch linear scheduler")
          self.scheduler = lr_scheduler.MultiStepLR(optimizer,
                                                    milestones = stream["decay_epoch"],
                                                    gamma = stream["decay_gamma"]
                                                    )
        else:
          print("\n\n>> Running with constant linear scheduler")
          self.scheduler = lr_scheduler.StepLR(optimizer,
                                                step_size = stream["decay_epoch"],
                                                gamma = stream["decay_gamma"]
                                              )

      elif self.scheduler_type == "exp":
        self.exp_init(stream, **kwags)

  def one_cycle_init(self, stream, **kwags):
    if kwags["max_lr_decay"]:
      stream["max_lr"] = stream["max_lr"] * stream["max_lr_decay_rate"] ** (self.current_epoch // stream["epochs"])

    if "max_lr_decay" in stream: stream.pop("max_lr_decay")
    stream.pop("max_lr_decay_rate")

    print("\n\n>> Running with 1cycle scheduler")
    stream["steps_per_epoch"] = self.iteration_per_epoch
    self.scheduler = lr_scheduler.OneCycleLR(self.optimizer, **stream)


  def exp_init(self, stream, **kwags):
    print("\n\n>> Running with exp scheduler")
    stream["decay_steps"] = stream["decay_steps"] * self.iteration_per_epoch
    self.scheduler = ExponentialStep(self.optimizer, **stream)