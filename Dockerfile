FROM python:3.11.9-bullseye
# Create User
ARG UID=1000
ARG GID=1000
RUN addgroup --gid $GID general_user && \
    adduser --system --disabled-password --disabled-login --uid $UID --ingroup general_user --shell /bin/sh general_user
# Create directories and set permissions
COPY . /lidagigs
WORKDIR /lidagigs
RUN chown -R $UID:$GID /lidagigs
# Install requirements and run code as general_user
RUN pip install --no-cache-dir -r requirements.txt
EXPOSE 5000
USER general_user
# CMD ["gunicorn", "src.Lidagigs:app", "-c", "gunicorn_config.py"]
CMD ["bash"]
